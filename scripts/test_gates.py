import copy, unittest
from build import release_ok, validate, ROOT, read
class Gates(unittest.TestCase):
    def test_exact_bytes(self):
        m={'fingerprint':'v4','files':{'movie.mp4':'hash'},'evidence_sha256':'source'}
        a={**m,'decision':'release','reviewed_contact_sheet':'export','scientific_review':'checked','visual_review':'checked','audio_review':'ASR and loudness'}
        self.assertTrue(release_ok(a,m))
        for field in ['fingerprint','files','evidence_sha256']:
            changed=copy.deepcopy(m);changed[field]='changed';self.assertFalse(release_ok(a,changed))
        self.assertFalse(release_ok(None,m))
    def test_missing_negation(self):
        ep=read(ROOT/'episodes/tt-003.json');validate(ep)
        ep['production']['segments'][5]['captions']=['This was a test of recovery after pollution stopped.']
        with self.assertRaises(AssertionError):validate(ep)
    def test_rights(self):
        ep=read(ROOT/'episodes/tt-002.json');ep['production']['assets'][0]['license_url']=''
        with self.assertRaises(AssertionError):validate(ep)
    def test_source(self):
        ep=read(ROOT/'episodes/tt-002.json');ep['evidence']['claims'][0]['location']=''
        with self.assertRaises(AssertionError):validate(ep)
if __name__=='__main__':unittest.main()
