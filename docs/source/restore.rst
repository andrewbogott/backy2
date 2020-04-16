.. include:: global.rst.inc

.. _restore:

Restore
=======

.. command-output:: backy2 restore --help

There are two possible restore options:

Full restore
------------

A full restore happens either into a file (i.e. an image file), to a device (e.g.
/dev/hda) or to a ceph/rbd-volume.

The target is specified by the URI schema. Examples::

    $ backy2 restore <version_uid> file:///var/lib/vms/myvm.img
    $ backy2 restore -f <version_uid> file:///dev/hdm
    $ backy2 restore <version_uid> rbd://pool/myvm_restore

If the target already exists as

- it is a device file
- the rbd volume exists
- the image file exists

you need to ``--force`` the restore. Without ``--force`` backy2 will break with
an error and give you a hint::

    backy2 restore 90fbbeb6-1fbe-11e7-9f25-a44e314f9270 file://tmp/T
        INFO: $ /home/dk/develop/backy2/env/bin/backy2 restore 90fbbeb6-1fbe-11e7-9f25-a44e314f9270 file://tmp/T
       ERROR: Target already exists: file://tmp/T
    Error opening restore target. You must force the restore.

.. NOTE:: When restoring to a ceph/rbd volume, backy2 will create this rbd
    volume for you if it does not exist.

If the restore-target is full of 0x00 bytes, you can use the ``-s`` or ``--sparse``
option for faster restores. With ``-s`` backy2 will not write (i.e. skip) empty
blocks or blocks that contain only 0x00 bytes.

Usually you can use ``-s`` if your restore target is

- a new/non-existing ceph/rbd volume
- a new/non-existing image file (backy2 will then create a sparse file)

.. CAUTION:: If you use ``-s`` on existing images, devices or files, restore-blocks which
    do not exist or contain only 0x00 bytes will not be written, so whatever
    random data was in there before the restore will remain.


Live-mount via NBD
------------------

backy2 has its own NBD server. So you can mount any existing backup of a
filesystem directly.

.. command-output:: backy2 nbd --help

Example::

    backy2 nbd -r 90fbbeb6-1fbe-11e7-9f25-a44e314f9270
        INFO: $ /home/dk/develop/backy2/env/bin/backy2 nbd -r 90fbbeb6-1fbe-11e7-9f25-a44e314f9270
        INFO: Starting to serve nbd on 127.0.0.1:10809
        INFO: You may now start
        INFO:   nbd-client -l 127.0.0.1 -p 10809
        INFO: and then get the backup via
        INFO:   modprobe nbd
        INFO:   nbd-client -N <version> 127.0.0.1 -p 10809 /dev/nbd0

You can then create a new nbd device with the given commands (as root)::

    # modprobe nbd
    # nbd-client -N 90fbbeb6-1fbe-11e7-9f25-a44e314f9270 127.0.0.1 -p 10809 /dev/nbd0
    Negotiation: ..size = 10MB
    bs=1024, sz=10485760 bytes

    # partprobe might throw a few WARNINGs because we're read-only
    partprobe /dev/nbd0
    mount -o ro,norecovery /dev/nbd0p1 /mnt

The norecovery is required as backy2 blocks all writes with the ``-r`` option.
When you're done::

    umount /mnt
    nbd-client -d /dev/nbd0

In the other console, backy2 will tell you that nbd has disconnected::

    INFO: [127.0.0.1:38316] disconnecting

You can then either reconnect or press ``ctrl+c`` to end the backy2 nbd server.

You may also mount the volume from another server. backy2 by default binds the
NBD server to 127.0.0.1 (i.e. localhost). For this server to be reachable from
the outside, bind to 0.0.0.0::

    backy2 nbd -a 0.0.0.0 -r 90fbbeb6-1fbe-11e7-9f25-a44e314f9270

You can also chose an appropriate port with the ``-p`` option.


Mount read-wite
~~~~~~~~~~~~~~~

In addition to providing read-only access, backy2 also allows *read-write* access
in a safe way. This means, the backup **will not be modified**.
The signature is mostly the same::

    backy2 nbd 90fbbeb6-1fbe-11e7-9f25-a44e314f9270
        INFO: $ /home/dk/develop/backy2/env/bin/backy2 nbd 90fbbeb6-1fbe-11e7-9f25-a44e314f9270
        INFO: Starting to serve nbd on 127.0.0.1:10809
        INFO: You may now start
        INFO:   nbd-client -l 127.0.0.1 -p 10809
        INFO: and then get the backup via
        INFO:   modprobe nbd
        INFO:   nbd-client -N <version> 127.0.0.1 -p 10809 /dev/nbd0
        INFO: nbd is read/write.

Of course you can then mount the volume read/write and fix all potential
filesystem errors or database files or you can modify data in any way you want::

    # modprobe nbd
    # nbd-client -N 90fbbeb6-1fbe-11e7-9f25-a44e314f9270 127.0.0.1 -p 10809 /dev/nbd0
    Negotiation: ..size = 10MB
    bs=1024, sz=10485760 bytes

    # partprobe /dev/nbd0
    # mount /dev/nbd0p1 /mnt
    # echo 'test' > /mnt/tmp/test  # example!

When you then disconnect from the nbd-client via::

    umount /mnt
    nbd-client -d /dev/nbd0

backy2 will do all the homework to create the copy-on-write backup::

    INFO: [127.0.0.1:46526] disconnecting
    INFO: Fixating version 430d4f4e-2f1d-11e7-b961-a44e314f9270 with 1 blocks (PLEASE WAIT)
    INFO: Fixation done. Deleting temporary data (PLEASE WAIT)
    INFO: Finished.

You can then safely press ``ctrl+c`` in backy2 in order to end the nbd server.

.. CAUTION:: If you ``ctrl+c`` before the last "INFO: Finished." is reported,
    your copy-on-write clone will not be written completely and thus be invalid.
    However, the original backup version **will in any case be valid**.

Writing to backy2 NBD will create a copy-on-write backup (example)::

    $ backy2 ls
    +---------------------+---------------+---------------+…
    |         date        | name          | snapshot_name |…
    +---------------------+---------------+---------------+…
    | 2017-05-02 09:53:58 | testbackup    | copy on write |…
    +---------------------+---------------+---------------+…
        INFO: Backy complete.

The name will be the same as the original backup, the snapshot name will be
``copy on write``.

.. NOTE:: You may safely delete the original version and the copy-on-write
    independently of each other.


Restore continuation
--------------------

If your backup target (=restore source) or your restore target are unstable,
it can happen that you're unable to restore a full backup due to service
interruptions on these storages.

In that case you can resume a stopped restore process, even if backy2 stops
working in strange ways (actually you may also just kill the backy2 process by
pressing ctrl+c or killing the process).

For hinting from where to start writing to the restore-target again, backy2
outputs ``Last ID`` as the hint which was the last block until which **all**
blocks have been written successfully to the restore-target.

.. NOTE:: This especially works even with asynchronuous writes as we have
   them when using the simultanuous_writes config variable.

You can then pass the last block-ID that you have seen during the restore
process to ``backy2 restore``. It's important however that you use the exactly
same parameters as before when restoring::

   $ backy2 restore 30d53cea-7ff8-11ea-9466-8931a4889813 file://test.img
       INFO: $ backy2 restore 30d53cea-7ff8-11ea-9466-8931a4889813 file://test.img
       INFO: Restore phase 1/2 (sparse) to null:// Read Queue [          ] Write Queue [          ] (0.4% 0.0MB/sØ ETA 1s) 
       INFO: Restore phase 2/2 (data) to null:// Read Queue [=         ] Write Queue [          ] (0.4% 0.0MB/sØ ETA 13s) Last ID: None
       INFO: Restore phase 2/2 (data) to null:// Read Queue [==========] Write Queue [          ] (20.7% 197.3MB/sØ ETA 4s) Last ID: 42
   ^CTraceback (most recent call last):
     File "/home/dk/develop/backy2/env/bin/backy2", line 11, in <module>
       load_entry_point('backy2', 'console_scripts', 'backy2')()
     File "/home/dk/develop/backy2/src/backy2/scripts/backy.py", line 749, in main
       func(**func_args)
     File "/home/dk/develop/backy2/src/backy2/scripts/backy.py", line 103, in restore
       backy.restore(version_uid, target, sparse, force, int(continue_from))
     File "/home/dk/develop/backy2/src/backy2/backy.py", line 380, in restore
       data_checksum = self.hash_function(data).hexdigest()
   KeyboardInterrupt

   $ backy2 restore 30d53cea-7ff8-11ea-9466-8931a4889813 file://test.img -c 42
       INFO: $ backy2 restore 30d53cea-7ff8-11ea-9466-8931a4889813 file://test.img -c 42
       INFO: Restore phase 1/2 (sparse) to null:// Read Queue [          ] Write Queue [          ] (16.8% 0.0MB/sØ ETA 0s) 
       INFO: Restore phase 2/2 (data) to null:// Read Queue [====      ] Write Queue [          ] (0.5% 0.0MB/sØ ETA 23s) Last ID: None
       INFO: Restore phase 2/2 (data) to null:// Read Queue [==========] Write Queue [          ] (38.3% 292.1MB/sØ ETA 2s) Last ID: 122
       INFO: Backy complete.

.. HINT:: If you don't see why ``-c 42`` has been used in the above command,
   you will need to scroll to the right as output is cut in this documentation.
   Then you'll see ``Last ID: 42``.

Edge-Cases
----------

Invalid blocks / versions
~~~~~~~~~~~~~~~~~~~~~~~~~

During full restore, backy2 will compare each restored block's checksum to the
stored checksum from the metadata store **no matter if the block has been
marked invalid previously**. If it encounters a difference, the block
and all versions containing this block will be marked *invalid* and a warning
will be given::

   ERROR: Checksum mismatch during restore for block 2558 (is: a134381a9760b5569cdaa2b1496483a5cef0428b2de351593599aaac4a5525e8dc97610a3cf515bce685d1e2a1e76c054c3438382588669a909e2073dac1a25c should-be: asd, block-valid: 0). Block restored is invalid. Continuing.
    INFO: Marked block invalid (UID 73923236eb5ttp7DJ6BdynMfwMnZamTF, Checksum asd. Affected versions: 90fbbeb6-1fbe-11e7-9f25-a44e314f9270, bc1af5e0-2f1c-11e7-b961-a44e314f9270, 0ffaf1ba-2f1d-11e7-b961-a44e314f9270, 2563c0a4-2f1d-11e7-b961-a44e314f9270, 430d4f4e-2f1d-11e7-b961-a44e314f9270

Even when encountering such an error, backy2 will continue to restore.

.. NOTE:: The philosophy behind this is that restores must allways succeed, even if there
    are errors in the data. Most times invalid data is on irrelevant places or can
    be fixed later. It's always worse to crash/break the restore process when an
    error occurs.

The ``null://`` target
----------------------

As there's the null://<size> source, there's also a null:// target. You may use
this for performance-testing or bottleneck-tests, but of course all "written"
data will just be lost.
Example::

    $ backy2 restore 30d53cea-7ff8-11ea-9466-8931a4889813 null://

