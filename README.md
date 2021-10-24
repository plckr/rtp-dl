# rtp-dl
This python script downloads each episode of the program, if more than one part available, it'll merge into a single file and finally convert it to mkv with correct language and title.

## usage
```
rtp-dl.py [ProgramID (Example: p1222)] [-e EpisodeNumber: Optional] [-s SeasonNumber: Optional]
```

## requirements
In order for this script to work, make sure you have all the python dependencies, listed in `requirements.txt`
Also, you need to have `ffmpeg` available in the command line