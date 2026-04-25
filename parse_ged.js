const fs = require('fs');

// Read GEDCOM file, handle CR-only line endings from MacFamilyTree
const raw = fs.readFileSync('My.ged', 'utf-8');
const lines = raw.replace(/\r\n/g, '\n').replace(/\r/g, '\n').split('\n');

const individuals = {};
const families = {};
const notes = {};
const objes = {};

let currentRecord = null;
let currentType = null;
let currentSubTag = null;

for (let i = 0; i < lines.length; i++) {
  const line = lines[i];
  const match = line.match(/^(\d+)\s+(.*)$/);
  if (!match) continue;

  const level = parseInt(match[1]);
  const rest = match[2];

  if (level === 0) {
    currentSubTag = null;
    // Check for record start: 0 @ID@ TYPE
    const recMatch = rest.match(/^@(\d+)@\s+(\w+)$/);
    if (recMatch) {
      const id = recMatch[1];
      const type = recMatch[2];
      currentType = type;
      if (type === 'INDI') {
        currentRecord = {
          id,
          givn: '',
          surn: '',
          secg: '',
          sex: '',
          birthDate: '',
          birthPlace: '',
          deathDate: '',
          deathPlace: '',
          occupation: '',
          residence: '',
          objes: [],
          fams: [],
          famc: [],
          notes: [],
          photoIds: []
        };
        individuals[id] = currentRecord;
      } else if (type === 'FAM') {
        currentRecord = {
          id,
          husb: '',
          wife: '',
          chil: [],
          marriageDate: '',
          marriagePlace: ''
        };
        families[id] = currentRecord;
      } else if (type === 'NOTE') {
        currentRecord = { id, text: '' };
        notes[id] = currentRecord;
      } else if (type === 'OBJE') {
        currentRecord = { id, file: '', form: '', title: '' };
        objes[id] = currentRecord;
      } else {
        currentRecord = null;
        currentType = null;
      }
    } else {
      currentRecord = null;
      currentType = null;
    }
    continue;
  }

  if (!currentRecord) continue;

  const tagMatch = rest.match(/^(\w+)\s*(.*)$/);
  if (!tagMatch) continue;

  const tag = tagMatch[1];
  const value = tagMatch[2].trim();

  if (currentType === 'INDI') {
    if (level === 1) {
      currentSubTag = tag;
      if (tag === 'GIVN') currentRecord.givn = value;
      else if (tag === 'SURN') currentRecord.surn = value;
      else if (tag === 'SECG') currentRecord.secg = value;
      else if (tag === 'SEX') currentRecord.sex = value;
      else if (tag === 'BIRT') currentSubTag = 'BIRT';
      else if (tag === 'DEAT') currentSubTag = 'DEAT';
      else if (tag === 'OCCU') currentRecord.occupation = value;
      else if (tag === 'RESI') currentSubTag = 'RESI';
      else if (tag === 'OBJE') {
        const objeRef = value.match(/@(\d+)@/);
        if (objeRef) currentRecord.objes.push(objeRef[1]);
      }
      else if (tag === 'FAMS') {
        const ref = value.match(/@(\d+)@/);
        if (ref) currentRecord.fams.push(ref[1]);
      }
      else if (tag === 'FAMC') {
        const ref = value.match(/@(\d+)@/);
        if (ref) currentRecord.famc.push(ref[1]);
      }
      else if (tag === 'NOTE') {
        const ref = value.match(/@(\d+)@/);
        if (ref) currentRecord.notes.push(ref[1]);
      }
      else if (tag === 'NAME') {
        // Only parse the first NAME (level 1) for givn/surn if not yet set
        // NAME format: "Given /Surname/"
        if (!currentRecord._nameProcessed) {
          const nameMatch = value.match(/^(.*?)\s*\/(.*?)\//);
          if (nameMatch) {
            if (!currentRecord.givn) currentRecord.givn = nameMatch[1].trim();
            if (!currentRecord.surn) currentRecord.surn = nameMatch[2].trim();
          }
          currentRecord._nameProcessed = true;
        }
      }
    } else if (level === 2) {
      if (tag === 'GIVN') currentRecord.givn = value;
      else if (tag === 'SURN') currentRecord.surn = value;
      else if (tag === 'SECG') currentRecord.secg = value;
      else if (currentSubTag === 'BIRT') {
        if (tag === 'DATE') currentRecord.birthDate = value;
        else if (tag === 'PLAC') currentRecord.birthPlace = value;
        else if (tag === 'ADDR') currentRecord.birthPlace = value;
      } else if (currentSubTag === 'DEAT') {
        if (tag === 'DATE') currentRecord.deathDate = value;
        else if (tag === 'PLAC') currentRecord.deathPlace = value;
      } else if (currentSubTag === 'RESI') {
        if (tag === 'ADDR') currentRecord.residence = value;
      }
    }
  } else if (currentType === 'FAM') {
    if (level === 1) {
      currentSubTag = tag;
      if (tag === 'HUSB') {
        const ref = value.match(/@(\d+)@/);
        if (ref) currentRecord.husb = ref[1];
      } else if (tag === 'WIFE') {
        const ref = value.match(/@(\d+)@/);
        if (ref) currentRecord.wife = ref[1];
      } else if (tag === 'CHIL') {
        const ref = value.match(/@(\d+)@/);
        if (ref) currentRecord.chil.push(ref[1]);
      } else if (tag === 'MARR') {
        currentSubTag = 'MARR';
      }
    } else if (level === 2) {
      if (currentSubTag === 'MARR') {
        if (tag === 'DATE') currentRecord.marriageDate = value;
        else if (tag === 'PLAC') currentRecord.marriagePlace = value;
      }
    }
  } else if (currentType === 'NOTE') {
    if (tag === 'CONT' || tag === 'CONC') {
      currentRecord.text += (currentRecord.text ? '\n' : '') + value;
    }
  } else if (currentType === 'OBJE') {
    if (level === 1) {
      if (tag === 'FILE') currentRecord.file = value;
      else if (tag === 'TITL') currentRecord.title = value;
    } else if (level === 2) {
      if (tag === 'FORM') currentRecord.form = value;
    }
  }
}

// Build photoIds for each individual from OBJE references
for (const indi of Object.values(individuals)) {
  indi.photoIds = [];
  for (const objeId of indi.objes) {
    const obje = objes[objeId];
    if (obje && obje.file) {
      // Extract the numeric ID from filename like "54203864.jpg"
      const fileId = obje.file.replace(/\.\w+$/, '');
      indi.photoIds.push(fileId);
    }
  }
  delete indi._nameProcessed;
}

const data = { individuals, families, notes };

fs.writeFileSync('data.json', JSON.stringify(data, null, 2), 'utf-8');

console.log(`Parsed:`);
console.log(`  Individuals: ${Object.keys(individuals).length}`);
console.log(`  Families: ${Object.keys(families).length}`);
console.log(`  Notes: ${Object.keys(notes).length}`);
console.log(`  Media objects: ${Object.keys(objes).length}`);

// Check photo coverage
let withPhotos = 0;
for (const indi of Object.values(individuals)) {
  if (indi.photoIds.length > 0) withPhotos++;
}
console.log(`  Individuals with photos: ${withPhotos}`);
