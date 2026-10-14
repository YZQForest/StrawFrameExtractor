"""Independent synthetic format fixtures; these are not research labels."""
import hashlib
import io
import json
from pathlib import Path
import struct
import tempfile
import threading
import unittest
import urllib.error
import urllib.request
import zipfile
import zlib

from strawframe.annotation.bundle import validate_bundle, save_bundle
from strawframe.annotation.server import create_server


def png(width, height, values):
    def chunk(kind, data):
        return struct.pack('>I', len(data)) + kind + data + struct.pack('>I', zlib.crc32(kind + data) & 0xffffffff)
    raw = b''.join(b'\0' + bytes(values[y*width:(y+1)*width]) for y in range(height))
    return b'\x89PNG\r\n\x1a\n' + chunk(b'IHDR', struct.pack('>IIBBBBB', width, height, 8, 0, 0, 0, 0)) + chunk(b'IDAT', zlib.compress(raw)) + chunk(b'IEND', b'')


def fixture(labels=None, valid=None, training=None, completed=True):
    labels = labels or [255, 0, 128, 0, 255, 128, 0, 0, 0, 0, 0, 0]
    valid = valid or [255]*11 + [0]
    training = training or [255 if not v or l in (128,64) else int(l==255) for l,v in zip(labels,valid)]
    n=sum(bool(v) for v in valid); s=sum(l==255 and bool(v) for l,v in zip(labels,valid)); u=sum(l==128 and bool(v) for l,v in zip(labels,valid)); d=sum(l==64 and bool(v) for l,v in zip(labels,valid))
    image=png(4,3,[140]*12)
    record={'sample_id':'synthetic_test_only','original_file_name':'synthetic.png','width':4,'height':3,'image_sha256':hashlib.sha256(image).hexdigest(),'image_path':'images/synthetic.png','mask_path':('human_masks' if completed else 'drafts')+'/synthetic_mask.png','valid_roi_path':'valid_roi/synthetic_valid.png','training_mask_path':('training_masks' if completed else 'draft_training_masks')+'/synthetic.png','metadata_path':'metadata/synthetic.json','status':'completed' if completed else 'draft','annotator':'TEST_ONLY','inspection':{'ground_roi_checked':True,'full_image_checked':True,'human_annotation_confirmed':True},'statistics':{'valid_pixels':n,'straw_pixels':s,'uncertain_pixels':u,'unmarked_pixels':d,'excluded_pixels':12-n,'coverage_lower_pp':100*s/n,'coverage_upper_pp':100*(s+u+d)/n,'coverage_pp':100*s/n if not u and not d else None}}
    files={record['image_path']:image,record['mask_path']:png(4,3,labels),record['valid_roi_path']:png(4,3,valid),record['training_mask_path']:png(4,3,training),record['metadata_path']:json.dumps(record).encode()}
    record.update(annotation_role='primary',session_id='synthetic-session')
    files[record['metadata_path']]=json.dumps(record).encode()
    manifest={'schema_version':'straw-annotation/2','session':{'id':'synthetic-session','annotator':'TEST_ONLY','role':'primary'},'records':[record],'file_sha256':{n:hashlib.sha256(b).hexdigest() for n,b in files.items()}}
    files['manifest.json']=json.dumps(manifest).encode()
    return pack(files),files


def pack(files):
    out=io.BytesIO()
    with zipfile.ZipFile(out,'w',zipfile.ZIP_STORED) as archive:
        for name, content in files.items(): archive.writestr(name,content)
    return out.getvalue()


class AnnotationBundleTests(unittest.TestCase):
    def test_interval_and_training_mapping(self):
        report,_=validate_bundle(fixture()[0])
        self.assertEqual(report['completed'],1)
        self.assertFalse(report['human_correctness_verified'])

    def test_draft_unmarked_is_separate(self):
        data,_=fixture(labels=[64]+[0]*11,completed=False)
        self.assertEqual(validate_bundle(data)[0]['drafts'],1)

    def test_unmarked_cannot_be_completed(self):
        with self.assertRaisesRegex(ValueError,'unmarked'):
            validate_bundle(fixture(labels=[64]+[0]*11)[0])

    def test_wrong_training_target_rejected(self):
        with self.assertRaisesRegex(ValueError,'mapping'):
            validate_bundle(fixture(training=[0]*12)[0])

    def test_corruption_rejected(self):
        _,files=fixture(); files['images/synthetic.png'] += b'corruption'
        with self.assertRaisesRegex(ValueError,'hash'):
            validate_bundle(pack(files))

    def test_traversal_rejected(self):
        _,files=fixture();files['../outside.txt']=b'no'
        with self.assertRaisesRegex(ValueError,'path'):
            validate_bundle(pack(files))

    def test_arithmetic_checked_independently(self):
        _,files=fixture(); m=json.loads(files['manifest.json']); r=m['records'][0];r['statistics']['coverage_lower_pp']=99
        files[r['metadata_path']]=json.dumps(r).encode();m['file_sha256'][r['metadata_path']]=hashlib.sha256(files[r['metadata_path']]).hexdigest();files['manifest.json']=json.dumps(m).encode()
        with self.assertRaisesRegex(ValueError,'coverage'):
            validate_bundle(pack(files))

    def test_unique_exports_preserve_previous_rater(self):
        with tempfile.TemporaryDirectory() as d:
            a=save_bundle(fixture()[0],Path(d));b=save_bundle(fixture()[0],Path(d))
            self.assertNotEqual(a['folder'],b['folder'])
            self.assertTrue((Path(a['folder'])/'human_masks/synthetic_mask.png').is_file())

    def test_loopback_service_save_and_token_gate(self):
        with tempfile.TemporaryDirectory() as d:
            server=create_server(output=Path(d),port=0)
            thread=threading.Thread(target=server.serve_forever,daemon=True);thread.start()
            try:
                info=json.load(urllib.request.urlopen(server.annotation_url+'api/catalog'))
                request=urllib.request.Request(server.annotation_url+'api/export',data=fixture()[0],method='POST')
                with self.assertRaises(urllib.error.HTTPError) as error: urllib.request.urlopen(request)
                self.assertEqual(error.exception.code,403)
                error.exception.close()
                request.add_header('X-Annotation-Token',info['token'])
                result=json.load(urllib.request.urlopen(request));self.assertEqual(result['completed'],1)
                request=urllib.request.Request(server.annotation_url+'api/export',data=b'not a zip',method='POST',headers={'X-Annotation-Token':info['token']})
                with self.assertRaises(urllib.error.HTTPError) as error: urllib.request.urlopen(request)
                self.assertEqual(error.exception.code,400)
                error.exception.close()
            finally: server.shutdown();server.server_close()


if __name__=='__main__': unittest.main()
