Here it will scanning a particular drive in my system and store the list of files and folders path in the firebase and gives the list of files and folders and only give the list of images and videos but not all other files , and it will also ask which drive should be scanned. And in this we can delete particular folder or file for that we have to give the command and location valves in this format
"deleteCommand": {
  "command": "holiday.jpg",
  "location": "D:\\Photos\\holiday.jpg"
}
"deleteCommand": {
  "command": "New folder",
  "location": "D:\\New folder"
}
"driveScan": [
  "D:\\Photos",
  "D:\\Photos\\holiday.jpg",
  "D:\\Videos\\movie.mp4"
]
