import subprocess
import sys


def trim_video(input_file, start_time, duration, output_file):
    command = [
        'ffmpeg',
        '-i', input_file,
        '-ss', start_time,
        '-t', duration,
        '-c', 'copy',
        output_file
    ]

    subprocess.run(command)


if __name__ == '__main__':
    if len(sys.argv) != 5:
        print('Usage: python video_trimmer.py <input_file> <start_time> <duration> <output_file>')
        sys.exit(1)

    input_file = sys.argv[1]
    start_time = sys.argv[2]
    duration = sys.argv[3]
    output_file = sys.argv[4]

    trim_video(input_file, start_time, duration, output_file)
