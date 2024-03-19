# s3ptools

Tools for working with KONAMI's proprietary [ASF](https://en.wikipedia.org/wiki/Advanced_Systems_Format) container file format, S3P.

# Tools

## s3pconvert.py

```
usage: s3pconvert.py [-h] [-o OUTPUT_PATH] input_path

Convert between ASF and S3P files.

positional arguments:
  input_path            S3P file to extract or extracted S3P directory to package

options:
  -h, --help            show this help message and exit
  -o OUTPUT_PATH, --output OUTPUT_PATH
                        directory (extract, package) or file (package) to output to
```

Generally the workflow of this tool involves unpacking, replacing `.asf` file(s), and repacking.

```bash
s3pconvert.py originals/file.s3p #extracts to ./file/
ffmpeg -i new_sound.mp3 ./file/2.asf #replace the second sound
s3pconvert.py file #packages ./file/ to ./file.s3p
```

## Notes

There's some unknown fields in the S3V header that are stored in `metadata.json`, they don't seem to matter but they can be modified and are respected when packaging.