import json
import re

with open('My.ged', 'r', encoding='utf-8') as f:
    raw = f.read()

lines = raw.replace('\r\n', '\n').replace('\r', '\n').split('\n')

individuals = {}
families = {}
notes = {}
objes = {}

current_record = None
current_type = None
# Track level-1 and level-2 context tags
l1_tag = None
l1_is_first_name = False

for line in lines:
    m = re.match(r'^(\d+)\s+(.*)$', line)
    if not m:
        continue
    level = int(m.group(1))
    rest = m.group(2)

    if level == 0:
        l1_tag = None
        rec_m = re.match(r'^@(\d+)@\s+(\w+)$', rest)
        if rec_m:
            rid = rec_m.group(1)
            rtype = rec_m.group(2)
            current_type = rtype
            if rtype == 'INDI':
                current_record = {
                    'id': rid, 'givn': '', 'surn': '', 'secg': '', 'sex': '',
                    'birthDate': '', 'birthPlace': '', 'deathDate': '', 'deathPlace': '',
                    'occupation': '', 'residence': '',
                    'objes': [], 'fams': [], 'famc': [], 'notes': [], 'photoIds': [],
                    '_nameCount': 0
                }
                individuals[rid] = current_record
            elif rtype == 'FAM':
                current_record = {
                    'id': rid, 'husb': '', 'wife': '', 'chil': [],
                    'marriageDate': '', 'marriagePlace': ''
                }
                families[rid] = current_record
            elif rtype == 'NOTE':
                current_record = {'id': rid, 'text': ''}
                notes[rid] = current_record
            elif rtype == 'OBJE':
                current_record = {'id': rid, 'file': '', 'form': '', 'title': ''}
                objes[rid] = current_record
            else:
                current_record = None
                current_type = None
        else:
            current_record = None
            current_type = None
        continue

    if current_record is None:
        continue

    tag_m = re.match(r'^(\w+)\s*(.*)', rest)
    if not tag_m:
        continue
    tag = tag_m.group(1)
    value = tag_m.group(2).strip()

    if current_type == 'INDI':
        if level == 1:
            l1_tag = tag
            if tag == 'NAME':
                current_record['_nameCount'] += 1
                l1_is_first_name = (current_record['_nameCount'] == 1)
                # Parse inline name: "Given Middle /Surname/"
                if l1_is_first_name:
                    nm = re.match(r'^(.*?)\s*/(.+?)/', value)
                    if nm:
                        if not current_record['givn']:
                            current_record['givn'] = nm.group(1).strip()
                        if not current_record['surn']:
                            current_record['surn'] = nm.group(2).strip()
            elif tag == 'SEX':
                current_record['sex'] = value
            elif tag == 'BIRT':
                pass  # handled at level 2
            elif tag == 'DEAT':
                pass
            elif tag == 'OCCU':
                current_record['occupation'] = value
            elif tag == 'RESI':
                pass
            elif tag == 'OBJE':
                ref = re.search(r'@(\d+)@', value)
                if ref:
                    current_record['objes'].append(ref.group(1))
            elif tag == 'FAMS':
                ref = re.search(r'@(\d+)@', value)
                if ref:
                    current_record['fams'].append(ref.group(1))
            elif tag == 'FAMC':
                ref = re.search(r'@(\d+)@', value)
                if ref:
                    current_record['famc'].append(ref.group(1))
            elif tag == 'NOTE':
                ref = re.search(r'@(\d+)@', value)
                if ref:
                    current_record['notes'].append(ref.group(1))
        elif level == 2:
            if l1_tag == 'NAME' and l1_is_first_name:
                if tag == 'GIVN':
                    current_record['givn'] = value
                elif tag == 'SURN':
                    current_record['surn'] = value
                elif tag == 'SECG':
                    current_record['secg'] = value
            elif l1_tag == 'BIRT':
                if tag == 'DATE':
                    current_record['birthDate'] = value
                elif tag == 'PLAC':
                    current_record['birthPlace'] = value
                elif tag == 'ADDR':
                    if not current_record['birthPlace']:
                        current_record['birthPlace'] = value
            elif l1_tag == 'DEAT':
                if tag == 'DATE':
                    current_record['deathDate'] = value
                elif tag == 'PLAC':
                    current_record['deathPlace'] = value
            elif l1_tag == 'RESI':
                if tag == 'ADDR':
                    current_record['residence'] = value

    elif current_type == 'FAM':
        if level == 1:
            l1_tag = tag
            if tag == 'HUSB':
                ref = re.search(r'@(\d+)@', value)
                if ref:
                    current_record['husb'] = ref.group(1)
            elif tag == 'WIFE':
                ref = re.search(r'@(\d+)@', value)
                if ref:
                    current_record['wife'] = ref.group(1)
            elif tag == 'CHIL':
                ref = re.search(r'@(\d+)@', value)
                if ref:
                    current_record['chil'].append(ref.group(1))
        elif level == 2:
            if l1_tag == 'MARR':
                if tag == 'DATE':
                    current_record['marriageDate'] = value
                elif tag == 'PLAC':
                    current_record['marriagePlace'] = value

    elif current_type == 'NOTE':
        if tag in ('CONT', 'CONC'):
            if current_record['text']:
                current_record['text'] += '\n' + value
            else:
                current_record['text'] = value

    elif current_type == 'OBJE':
        if level == 1:
            if tag == 'FILE':
                current_record['file'] = value
            elif tag == 'TITL':
                current_record['title'] = value
        elif level == 2:
            if tag == 'FORM':
                current_record['form'] = value

# Build photoIds
for indi in individuals.values():
    indi['photoIds'] = []
    for obje_id in indi['objes']:
        obje = objes.get(obje_id)
        if obje and obje['file']:
            file_id = re.sub(r'\.\w+$', '', obje['file'])
            indi['photoIds'].append(file_id)
    del indi['_nameCount']

data = {'individuals': individuals, 'families': families, 'notes': notes}

with open('data.json', 'w', encoding='utf-8') as f:
    json.dump(data, f, ensure_ascii=False, indent=2)

print(f"Parsed:")
print(f"  Individuals: {len(individuals)}")
print(f"  Families: {len(families)}")
print(f"  Notes: {len(notes)}")
print(f"  Media objects: {len(objes)}")

with_photos = sum(1 for i in individuals.values() if i['photoIds'])
print(f"  Individuals with photos: {with_photos}")
