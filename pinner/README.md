# Pin Tool

This tool is currently used mainly for:

1) Inspecting resident memory and locality
2) Generating and inspecting pinlist.meta used by Android's PinnerService

For memory inspection, it allows probing live memory and providing the memory
locations that are resident which can be used for diagnosis or as part of PGO
optimizations.

## Build and Install the tool

To build and push the binary to device
```
mm pintool
and push $ANDROID_REPO/out/target/product/<lunchtarget>/system/bin/pintool /data/local/tmp/pintool
adb shell
cd /data/local/tmp/pintool
```


## How to use the tool to generate pinner files

Here are some sample use cases for this tool.

### Sample Use Case 1: Probe Resident Memory for a mapped file or library and dump to console

Executing the following command and providing the path to a library mapped by a process
it will dump the resident memory ranges.

```
./pintool file <path_to_your_library> --gen-probe --dump
```

Note: you can use any kind of mapped file such as .so, .apk, etc.

### Sample Use Case 2: Probe per-file Resident Memory for a mapped apk file and dump to console

Executing this command will inspect resident memory for a zip file and dump
per-file breakdowns.

```
./pintool file <path_to_myfile.apk> --zip --gen-probe --dump
```

### Sample Use Case 3: Probe per-file resident memory for a mapped apk, dump and generate pinlist.meta
```
./pintool file <path_to_myfile.apk> --zip --gen-probe --dump -o pinlist.meta
```

### Sample Use Case 4: Probe per-file resident memory and filter it with a provided pinconfig
```
./pintool file <path_to_myfile.apk> --zip --gen-probe --pinconfig pinconfig.txt --dump -o pinlist.meta
```

### Sample Use Case 5: Dump contents of a provided pinlist.meta file
```
./pintool pinlist pinlist.meta --dump -v
```

### Sample Use Case 6: Read a zip and filter based on a pinconfig file and generate pinlist.meta without probing

This will skip doing any probing and it will just apply filtering based on the pinconfig.txt, this is helpful
in cases where you do not intend to do any kind of PGO probing and know exactly what ranges you want to pin within your file

```
./pintool file <path_to_myfile.apk> --zip --pinconfig pinconfig.txt --dump -o pinlist.meta
```

### Sample Use Case 7: Load an existing zip probe and inspect its per-file contents

```
./pintool file /data/app/~~tmTrs5_XINwbpYWroRu5rA==/org.chromium.trichromelibrary_602300034-EFoOwMgVNBbwkMnp9zcWbg==/base.apk --zip --use-probe pinlist.meta --dump
```


## Pinconfig File Structure

Pinconfig files specify a custom filter to be applied on top of a generated or provided memory probe
it should specify a subset of files and optionally ranges within those files to be matched against
and subsequently kept in case a pinlist.meta is generated.

A `pinconfig.txt` is just a list of files with a key value pair separated by a newline.

`pinconfig.txt` structure pattern:
```
(file <file>
[offset <value>
length <value>])*
```
where:
<file>
    Filename as a string, the parser will do a contains like operation (e.g. GLOB(*<file>*)) to match against files
    within the zip file and stop on first match.
<value>
    Unsigned integer value

Note: `offset` and `length` tokens are optional and if ommited, the whole file will be considered desired.


Example `pinconfig.txt`:
```
file lib/arm64-v8a/libcrashpad_handler_trampoline.so
file libmonochrome_64.so
offset 1000
len 50000
file libarcore_sdk_c.so
```

## Pinlist.meta files

"pinlist.meta" files are consumed by PinnerService.

These files specify a list of memory ranges to be pinned (mlocked).
If Android's PinnerService allows your app pinning, it will read the pinlist.meta
file from inside your apk's assets folder (assets/pinlist.meta) and pin based
on the specified ranges.

Note: The PinnerService will need to support pinning your apk in order for the
pinlist.meta file to be used.

A pinlist.meta file is a binary file with a set of tuples of OFFSET and LENGTH
stored in Big Endian format.

4 byte: OFFSET
4 byte: LEN

pinlist.meta
```
OFFSET LEN*
```

So to read those files, it is usually helpful to use the `pintool`.

## Other potential uses

Outside of pinner service, the tool can be used to inspect resident memory for
any file in memory.

## Extra information

the pinlist.meta depends on the apk contents and needs to be regenrated if
you are pushing a new version of your apk.

## Tips for better pinning

Take the steps listed below before generating your pinlist to improve its quality.

### Disable disk read-ahead before generating the pinlist

Disk read-ahead will add pages to your pinlist that are not actually accessed.
Disable disk read-ahead to reduce the size of your pinned memory by dropping
unnecessary regions from the pinlist.

Before invoking `pintool --gen-probe`, disable disk read-ahead:
```
echo 1 > /sys/block/<block_device>/queue/read_ahead_kb
```
Replace <block_device> with the filesystem where the path to your `.apk` or library is hosted. You can find this information in the output of `df`.

If you are unsure if read ahead is currently enabled, you can just query the value instead:
```
cat /sys/block/<block_device>/queue/read_ahead_kb
```

This setting is reverted to the default after a reboot.

### Drop the page cache before generating the pinlist

Before taking a probe, it is a good idea to drop the page cache to reduce the amount of pages that
are unrelated to your CUJ and start fresh loading new memory.

In order to drop the page cache you can run this command:
```
echo 3 > /proc/sys/vm/drop_caches
```