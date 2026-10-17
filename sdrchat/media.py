import io
import subprocess

class MediaEncoder:
    image_max_edge=1600
    image_quality=80
    audio_bitrate_kbps=64

    def _encode_image(self, path, original):
        from PIL import Image, ImageOps
        with Image.open(path) as image:
            if getattr(image, 'n_frames', 1) != 1 or image.width * image.height > 40000000:
                return (original, path.name)
            image = ImageOps.exif_transpose(image)
            ext = path.suffix.lower()
            if ext == '.png' or 'A' in image.getbands():
                out = io.BytesIO()
                image.save(out, format='PNG', optimize=True)
                candidate, name = (out.getvalue(), path.stem + '.png')
            else:
                image = image.convert('RGB')
                image.thumbnail((self.image_max_edge, self.image_max_edge), Image.Resampling.LANCZOS)
                out = io.BytesIO()
                image.save(out, format='JPEG', quality=self.image_quality, optimize=True, progressive=True)
                candidate, name = (out.getvalue(), path.stem + '.jpg')
            return (candidate, name) if len(candidate) < len(original) else (original, path.name)

    def _encode_audio(self, path, original):
        if path.suffix.lower() in ('.ogg', '.opus'):
            return (original, path.name)
        result = subprocess.run(['ffmpeg', '-nostdin', '-v', 'error', '-i', str(path), '-vn', '-c:a', 'libopus', '-b:a', '%dk' % self.audio_bitrate_kbps, '-vbr', 'on', '-compression_level', '10', '-ar', '48000', '-f', 'ogg', 'pipe:1'], capture_output=True, timeout=300, check=True)
        candidate = result.stdout
        return (candidate, path.stem + '.ogg') if 0 < len(candidate) < len(original) else (original, path.name)
