
HOST="" # hostname/ip for the Shapes server
PORT=80 # port for the Shapes server
DO_HOST="" # hostname/ip for the DO server
DO_PORT=80 # port for the DO server 
DO_URL = 'http://%s:%d/do/' % (DO_HOST, DO_PORT)
DO_USER=""  	#username for DO repository
DO_PASSWORD="" 	#password for DO repository
SHAPE_URL = 'http://' + HOST + ':' + str(PORT) +'/shapes/%s/'
FILE_URL = 'http://' + HOST + ':' + str(PORT) +'/shapes/file/%s/'
MASK_URL = 'http://' + HOST + ':' + str(PORT) +'/shapes/mask/%s/'
CATEGORY_URL =  'http://' + HOST + ':' + str(PORT) +'/cats/%s/'
