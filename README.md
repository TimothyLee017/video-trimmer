# Video Trimmer

A simple and effective tool for trimming video files to desired lengths.

## Features
- Easily trim video files without re-encoding.
- Supports various popular video formats (MP4, AVI, MKV, etc.).
- User-friendly command-line interface.

## Installation
1. **Clone the repository**:
   ```bash
   git clone https://github.com/TimothyLee017/video-trimmer.git
   cd video-trimmer
   ```
2. **Install dependencies**:
   ```bash
   npm install
   ```

## Usage
To trim a video file, use the following command:
```bash
node trimmer.js <input-file> <start-time> <end-time>
```

### Example
Trimming a video from 00:01:30 to 00:02:45:
```bash
node trimmer.js myvideo.mp4 00:01:30 00:02:45
```

## Contributing
If you want to contribute to this project, please fork the repository and submit a pull request with your changes.

## License
This project is licensed under the MIT License.