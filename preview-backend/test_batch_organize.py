import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path


class BatchOrganizationTest(unittest.TestCase):
    def test_merges_tags_and_rolls_back_stale_selection(self):
        with tempfile.TemporaryDirectory() as folder:
            source = Path(__file__).resolve().parent
            for name in ('main.py', 'local_auth.py', 'record_export.py', 'excel_export.py', 'attachments.py'):
                shutil.copy2(source / name, folder)
            result = subprocess.run([sys.executable, '-X', 'utf8', '-c', '''
import json
from fastapi import HTTPException
from main import BatchOrganization, RecordCreate, RecordUpdate, create_record, update_record, organize_records, get_db

ids = [create_record(RecordCreate(content=text))['record']['id'] for text in ('第一条', '第二条')]
update_record(ids[0], RecordUpdate(tags=['原有']))
request = BatchOrganization(ids=[*ids, ids[0]], category='项目归档', tag='跟进')
assert organize_records(request) == {'updated': 2}
assert organize_records(request) == {'updated': 0}
try:
    organize_records(BatchOrganization(ids=[ids[0], 999999], category='错误分类'))
except HTTPException as error:
    assert error.status_code == 409
else:
    raise AssertionError('missing selection should reject the whole batch')
with get_db() as db:
    rows = db.execute('SELECT category, tags FROM records ORDER BY id').fetchall()
    assert [row['category'] for row in rows] == ['项目归档', '项目归档']
    assert [json.loads(row['tags']) for row in rows] == [['原有', '跟进'], ['跟进']]
    assert db.execute('SELECT count(*) FROM record_versions').fetchone()[0] == 3
'''], cwd=folder, capture_output=True, text=True, encoding='utf-8', timeout=20)
            self.assertEqual(result.returncode, 0, result.stdout + result.stderr)


if __name__ == '__main__':
    unittest.main()
