import json
import argparse
from io import BufferedReader, BufferedWriter, BytesIO
from enum import Enum
from pathlib import Path

ENDIANNESS = 'little'
METADATA_FILENAME = 'metadata.json'

class Format(Enum):
    S3P = b'S3P0'
    S3V = b'S3V0'

class BinaryReader(object):
    def __init__(self, file: BufferedReader) -> None:
        self.file = file

    def seek(self, pointer: int) -> None:
        self.file.seek(pointer)

    def tell(self) -> int:
        return self.file.tell()

    def peek(self, num_bytes: int) -> bytes:
        return self.file.peek()[:num_bytes]

    def read(self, length: int) -> bytes:
        return self.file.read(length)

    def read_u32(self) -> int:
        return int.from_bytes(self.file.read(0x4), ENDIANNESS)

class BinaryWriter(object):
    def __init__(self) -> None:
        self.buffer = BytesIO()

    def __len__(self) -> None:
        return self.buffer.tell()

    def tell(self) -> int:
        return self.buffer.tell()

    def write(self, value: bytes) -> None:
        self.buffer.write(value)

    def write_u32(self, value: int) -> None:
        self.buffer.write(value.to_bytes(0x4, ENDIANNESS))

    def read(self) -> bytes:
        return self.buffer.getvalue()

def main() -> None:
    parser = argparse.ArgumentParser(description='Convert between ASF and S3P files.')

    parser.add_argument(dest='input_path', help='S3P file to extract or extracted S3P directory to package', type=Path)
    parser.add_argument('-o', '--output', dest='output_path', help='directory (extract, package) or file (package) to output to', type=Path, default=Path.cwd())

    args = parser.parse_args()
    input_path = args.input_path
    output_path = args.output_path

    # if the input is a file verify it is an S3P and dump
    if input_path.is_file():
        if not output_path.is_dir():
            print('output path must be a directory')
            exit()

        # create the output directory
        if not output_path.is_dir():
            print('output path must be a directory for extraction')
            exit()

        output_directory = Path(output_path, input_path.stem)
        output_directory.mkdir(exist_ok=True)

        # read the s3p
        with open(input_path, 'rb') as input_file:
            reader = BinaryReader(input_file)
            format = Format(reader.read(0x4))
            if format != Format.S3P:
                print('input file not an S3P file')
                exit()

            num_s3v = reader.read_u32()

            # read each s3v
            metadata = []
            for index in range(num_s3v):
                start_pointer = reader.read_u32()
                length = reader.read_u32()
                return_pointer = reader.tell() #keep pointer to read next s3v

                # read the s3v
                reader.seek(start_pointer)
                s3v_file = reader.read(length)
                s3v_reader = BinaryReader(BytesIO(s3v_file))

                format = Format(s3v_reader.read(0x4))
                if format != Format.S3V:
                    print('invalid S3V file within S3P')
                    exit()

                asf_pointer = s3v_reader.read_u32() #relative to s3v
                asf_length = s3v_reader.read_u32()
                unk1 = s3v_reader.read_u32() #not u32
                unk2 = s3v_reader.read_u32() #usually 0
                unk3 = s3v_reader.read_u32() #unk, 512 for voices
                unk4 = s3v_reader.read_u32() #usually 0
                unk5 = s3v_reader.read_u32() #usually 0

                # assumptions
                assert(asf_pointer == 32)

                # read and dump the asf
                s3v_reader.seek(asf_pointer)
                asf = s3v_reader.read(asf_length)

                # [s3p name]/[index].asf
                asf_output_name = f'{index}.asf'
                asf_output_path = Path(output_directory, asf_output_name)
                with open(asf_output_path, 'wb+') as asf_output_file:
                    asf_output_file.write(asf)

                # store the metadata
                metadata.append({
                    'filename': asf_output_name,
                    'unk1': unk1,
                    'unk2': unk2,
                    'unk3': unk3,
                    'unk4': unk4,
                    'unk5': unk5,
                })

                # return to read the next s3v
                reader.seek(return_pointer)
            
            # dump the metadata
            metadata_output_path = Path(output_directory, METADATA_FILENAME)
            with open(metadata_output_path, 'w+') as metadata_file:
                metadata_file.write(json.dumps(metadata, indent=4))
    # if the input is a directory verify it is a dumped S3P and repack
    else:
        # ensure the input directory is a dumped s3p
        metadata_path = Path(input_path, METADATA_FILENAME)
        if not metadata_path.exists():
            print('input directory is not a dumped S3P')
            exit()

        # read the metadata
        with open(metadata_path, 'r') as metadata_file:
            metadata = json.load(metadata_file)

        # convert each asf file into s3v
        s3vs = []
        for s3v_metadata in metadata:
            # read the asf file into memory
            asf_path = Path(input_path, s3v_metadata['filename'])
            with open(asf_path, 'rb') as asf_file:
                asf = asf_file.read()

            # construct the s3v
            s3v = BinaryWriter()
            s3v.write(Format.S3V.value)
            s3v.write_u32(32)
            s3v.write_u32(len(asf))
            s3v.write_u32(s3v_metadata['unk1'])
            s3v.write_u32(s3v_metadata['unk2'])
            s3v.write_u32(s3v_metadata['unk3'])
            s3v.write_u32(s3v_metadata['unk4'])
            s3v.write_u32(s3v_metadata['unk5'])
            s3v.write(asf)
            s3vs.append(s3v)

        # pack the s3vs into an s3p
        s3p = BinaryWriter()
        s3p.write(Format.S3P.value)

        # write the header
        s3p.write_u32(len(s3vs))
        s3v_pointer = 8 + 8 * len(s3vs)
        for s3v in s3vs:
            s3p.write_u32(s3v_pointer)
            s3p.write_u32(len(s3v))
            s3v_pointer += len(s3v)

        # write the s3vs
        for s3v in s3vs:
            s3p.write(s3v.read())

        # write the terminator
        s3p.write_u32(len(s3p))

        # if output to dir then [output dir]/[input name].s3p
        # if output to file then [output name]
        if output_path.is_dir():
            s3p_output_path = Path(output_path, input_path.with_suffix('.s3p').name)
        else:
            s3p_output_path = output_path

        # write the s3p to the output file
        with open(s3p_output_path, 'wb+') as s3p_output_file:
            s3p_output_file.write(s3p.read())

if __name__ == '__main__':
    main()