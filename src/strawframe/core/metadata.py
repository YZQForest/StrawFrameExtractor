import csv, os
from decimal import Decimal, ROUND_HALF_UP

FIELDS='frame_id source_video source_video_path video_id output_filename output_path timestamp_sec timestamp_hms extract_index original_fps original_fps_ratio original_width original_height original_duration_sec extract_fps output_format output_width output_height source_frame_index video_codec created_at source_pts source_time_base source_timestamp_sec timestamp_definition run_id'.split()

def decimal_time(value):
    return format(Decimal(value.numerator)/Decimal(value.denominator),'.9f')

def millis(value):
    return int((Decimal(value.numerator)*1000/Decimal(value.denominator)).quantize(Decimal(1),rounding=ROUND_HALF_UP))

def hms(value):
    ms=millis(value); hours,ms=divmod(ms,3600000); minutes,ms=divmod(ms,60000); seconds,ms=divmod(ms,1000)
    return f'{hours:02d}:{minutes:02d}:{seconds:02d}.{ms:03d}'

class MetadataWriter:
    def __init__(self,path):
        exists=path.exists() and path.stat().st_size>0
        self.file=path.open('a',encoding='utf-8-sig',newline='')
        self.writer=csv.DictWriter(self.file,fieldnames=FIELDS)
        if not exists: self.writer.writeheader(); self.file.flush()
    def write(self,row):
        position = self.file.tell()
        try:
            self.writer.writerow(row); self.file.flush(); os.fsync(self.file.fileno())
        except Exception:
            # Roll back a partial CSV row if a write fails (e.g. disk full).
            try:
                self.file.seek(position); self.file.truncate(); self.file.flush()
            except OSError:
                pass
            raise
    def close(self): self.file.close()
