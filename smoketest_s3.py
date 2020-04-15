#!/usr/bin/env python3

import os
import shutil
import random
import json
import hashlib
import math
from backy2.scripts.backy import hints_from_rbd_diff
from backy2.logging import init_logging
from backy2.utils import backy_from_config
from backy2.config import Config as _Config
from functools import partial
import logging

kB = 1024
MB = kB * 1024
GB = MB * 1024

HASH_FUNCTION = hashlib.sha512

def patch(path, filename, offset, data=None):
    """ write data into a file at offset """
    filename = os.path.join(path, filename)
    if not os.path.exists(filename):
        open(filename, 'wb')
    with open(filename, 'r+b') as f:
        f.seek(offset)
        f.write(data)


def same(f1, f2):
    """ returns False if files differ, True if they are the same """
    d1 = open(f1, 'rb').read()
    d2 = open(f1, 'rb').read()
    return d1 == d2


class TestPath():
    path = '_smoketest'

    def __enter__(self):
        os.mkdir(self.path)
        return self.path


    def __exit__(self, type, value, traceback):
        shutil.rmtree(self.path)


with TestPath() as testpath:
    from_version = None
    init_logging(testpath+'/backy.log', logging.INFO)

    version_uids = []
    old_size = 0
    initdb = True
    for i in range(100):
        print('Run {}'.format(i+1))
        hints = []
        if old_size and random.randint(0, 10) == 0:  # every 10th time or so do not apply any changes.
            size = old_size
        else:
            size = 32*4*kB + random.randint(-4*kB, 4*kB)
            if size > old_size:
                hints.append({'offset': old_size, 'length': size-old_size, 'exists': 'true'})
            if size < old_size:
                last_block_offset = math.floor(size/(4*kB))*4*kB
                hints.append({'offset': last_block_offset, 'length': size-last_block_offset, 'exists': 'true'})
            old_size = size
            for j in range(random.randint(0, 10)):  # up to 10 changes
                if random.randint(0, 1):
                    patch_size = random.randint(0, 4*kB)
                    data = os.urandom(patch_size)
                    #exists = True
                    exists = "true"
                else:
                    patch_size = random.randint(0, 4*4*kB)  # we want full blocks sometimes
                    data = b'\0' * patch_size
                    #exists = False
                    exists = "false"
                offset = random.randint(0, size-1-patch_size)
                print('    Applied change at {}:{}, exists {}'.format(offset, patch_size, exists))
                patch(testpath, 'data', offset, data)
                hints.append({'offset': offset, 'length': patch_size, 'exists': exists})
        # truncate?
        open(os.path.join(testpath, 'data'), 'r+b').truncate(size)

        print('  Applied {} changes, size is {}.'.format(len(hints), size))
        open(os.path.join(testpath, 'hints'), 'w').write(json.dumps(hints))

        # create backy
        config = """
        [DEFAULTS]
        logfile: /var/log/backy.log
        block_size: 4096
        hash_function: sha512
        lock_dir: /tmp
        process_name: backy2

        [MetaBackend]
        type: backy2.meta_backends.sql
        engine: sqlite:///{testpath}/backy.sqlite

        [DataBackend]
        type: backy2.data_backends.s3
        aws_access_key_id: minioadmin
        aws_secret_access_key: minioadmin
        #aws_secret_access_key_file:
        bucket_name: backy2
        #region_name:
        endpoint_url: http://localhost:9000/
        #signature_version:
        use_ssl: false
        #bucket_name:
        #addressing_style: path
        #disable_encoding_type: false
        simultaneous_writes: 20
        simultaneous_reads: 20
        #bandwidth_read: 78643200
        #bandwidth_write: 78643200

        [NBD]
        cachedir: /tmp

        [io_file]
        simultaneous_reads: 5

        [io_rbd]
        ceph_conffile: /etc/ceph/ceph.conf
        simultaneous_reads: 10
        """.format(testpath=testpath)
        Config = partial(_Config, cfg=config)
        backy = backy_from_config(Config)(initdb=initdb)
        initdb = False
        version_uid = backy.backup(
            'data-backup',
            'snapshot-name',
            'file://'+os.path.join(testpath, 'data'),
            from_version and hints_from_rbd_diff(open(os.path.join(testpath, 'hints')).read()) or None,
            from_version
            )
        backy.close()
        version_uids.append(version_uid)

        try:
            backy = backy_from_config(Config)()
            assert backy.scrub(version_uid) == True
            backy.close()
            print('  Scrub successful')
            backy = backy_from_config(Config)()
            assert backy.scrub(version_uid, 'file://'+os.path.join(testpath, 'data')) == True
            backy.close()
            print('  Deep scrub successful')
            backy = backy_from_config(Config)()
            backy.restore(version_uid, 'file://'+os.path.join(testpath, 'restore'), sparse=False, force=False)
            backy.close()
            assert same(os.path.join(testpath, 'data'), os.path.join(testpath, 'restore')) == True
            os.unlink(os.path.join(testpath, 'restore'))
            print('  Restore successful')
        except AssertionError:
            import pdb; pdb.set_trace()

        from_version = version_uid

        # delete old versions
        if len(version_uids) > 10:
            backy = backy_from_config(Config)()
            backy.rm(version_uids.pop(0))
            backy.close()

        if (i%7) == 0:
            backy = backy_from_config(Config)()
            backy.cleanup_fast(dt=0)
            backy.close()
    #import pdb; pdb.set_trace()
