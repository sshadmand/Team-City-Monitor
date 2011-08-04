#Your TeamCity Base URL. No trailing slash. Example: http://www.yourname.com
BASE_TC_URL = "http://www.yourdomain.com"

#Team City user login information
TC_USERNAME = "admin"
TC_PW = "..."

#HTML <EMBED> code of a sound file to play if there is a build error
#Example: <embed src="http://www.sounds.com/yoursound.wav"  autoplay="true" autostart="True" type="audio/wav" style="width:1px;height:1px" loop="true" />"""
EMBED_SOUND_HTML = """<embed src="yoursound.wav"  autoplay="true" autostart="True" type="audio/wav" style="width:1px;height:1px" loop="true" />"""

#List of TeamCity build ids that you want to track
TRACKED_BUILD_IDS = ["bt2", "bt4", "bt5", "bt6", "bt7", "bt8"]

#Google API key used to generate graphs. 
#You may need to generate your own if you have not already done so on google
GOOGLE_API_KEY = ""
