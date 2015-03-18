##############################################
##SCRIPT BY  :  Ang Shimin
##CREATED    :  25 Nov 2014
##INPUT      :
##DESCRIPTION : This code checks file input is in place, mode 0 checks all files, mode 1 checks specific file from parameters
##D_VERSION    :  1.0.0
##		1.0.1 batch retrieves, more efficient
##P_VERSION  : 1.0.0
##	       1.1.0 Added --UDFCheck for UDF name --UDFRunVal for value of UDF, if match, check files
##############################################

import socket
from sys import exit
import sys
import getopt
import glsapiutil
import re
from xml.dom.minidom import parseString

#HOSTNAME = 'http://'+HOST+':8080'
VERSION = "v2"
BASE_URI = ""
DEBUG = False
api = None

def checkFileExistence(limsidArr):
	checkArr = []
	ignoreList = [ "QC Assignment Log File", "QC Assignment Report", "FileGeneration.log" ]	
	
	## Batch retrieve
	lXML = '<ri:links xmlns:ri="http://genologics.com/ri">'
	
	for limsid in limsidArr:
                link = '<link uri="' + BASE_URI + 'artifacts/' + limsid + '" rel="artifacts"/>'
                lXML += link
        lXML += '</ri:links>'
        gXML = api.getBatchResourceByURI( BASE_URI + "artifacts/batch/retrieve", lXML )
        gDOM = parseString( gXML )	
		
	## get name
	Nodes = gDOM.getElementsByTagName( "art:artifact" )

	for artifact in Nodes:
        	temp = artifact.getElementsByTagName( "name" )
        	
		## getInnerXml gets string from between tags
        	oName = api.getInnerXml(temp[0].toxml(), "name" )		
					
		## check existence
		isFile = artifact.getElementsByTagName( "file:file" )
		
		## if there is no file in this node, append the missing file's name
		if(len(isFile) < 1):
			checkArr.append(oName)

		## Remove ignores, due to "QC Assign" always with this script
		for name in checkArr:
			for ignore in ignoreList:
				if name == ignore:
					checkArr.remove(ignore)
					break

	return checkArr

def getOutputLimsid( limsid ):
	fileLimsidArr = []

	## Access artifact limsid from process XML	
	gURI = BASE_URI + "processes/" + limsid
	gXML = api.getResourceByURI( gURI )
	gDOM = parseString( gXML )
	IOMaps = gDOM.getElementsByTagName( "input-output-map" )

	for IOMap in IOMaps:
		output = IOMap.getElementsByTagName( "output" )
                oType = output[0].getAttribute( "output-type" )
                ogType = output[0].getAttribute( "output-generation-type" )
		
		## Both resultFile and sharedResultFile
                if (oType == "SharedResultFile" or oType == "ResultFile") and (ogType == "PerAllInputs" or ogType == "PerReagentLabel"):
			fileLimsidArr.append(output[0].getAttribute( "limsid" ))
	
	## use set() to rid of duplicates
	unique = set(fileLimsidArr)
	fileLimsidArr = list(unique)	

	return fileLimsidArr

def getHostname():

        response = ""
        ## retrieve host name using UNIX command
        temp = socket.gethostname()
        response = "http://" + temp + ".gis.a-star.edu.sg:8080"
        
	return response

def setBASEURI( hostname ):

        global BASE_URI
        BASE_URI = hostname + "/api/" + VERSION + "/"

def checkRunUDF():

        pURI = BASE_URI + "processes/" + args[ "processID" ]
        pXML = api.getResourceByURI( pURI )
        pDOM = parseString( pXML )

	UDFInput = api.getUDF( pDOM, args[ "UDF" ] )
        if not UDFInput == args[ "UDFVal" ]:
        	exit()

def main():

	global api
	global args
	args = {}

	reponse = ""
	ind_fileLimsidArr = []
	checkArr = []

	opts, extraparams = getopt.getopt(sys.argv[1:], "u:p:l:m:f:", ["checkUDF=", "UDFRunVal="])
	for o,p in opts:
		if o == '-u':
			args[ "username" ] = p
		elif o == '-p':
			args[ "password" ] = p
		elif o == '-l':
			args[ "processID" ] = p
		elif o == '-m':
			args[ "fileCheckMode" ] = p
		elif o == '-f':
			args[ "file" ] = p
			ind_fileLimsidArr.append(args[ "file" ])

		elif o == '--checkUDF':
			args[ "UDF" ] = p
		elif o == '--UDFRunVal':
			args[ "UDFVal" ] = p

	HOSTNAME = getHostname()
	setBASEURI(HOSTNAME)
	
	api = glsapiutil.glsapiutil()
	api.setHostname( HOSTNAME )
	api.setVersion( VERSION )
	api.setup( args[ "username" ], args[ "password" ] )
	
	## if UDF value matches, run script
	if "UDF" in args.keys():
		checkRunUDF()

	try:
		## mode 0 checks all files
		if(args[ "fileCheckMode" ] == "0"):
			fileLimsidArr = getOutputLimsid(args[ "processID" ])
			checkArr = checkFileExistence(fileLimsidArr)

		## mode 1 checks specific files
		elif(args[ "fileCheckMode" ] == "1"):
			checkArr = checkFileExistence(ind_fileLimsidArr)
#			print len(checkArr)


		if(len(checkArr) > 0):
                                errorMsg = "Required file(s) listed below are not present: " + "\n"
				
				for name in checkArr:
					errorMsg += "-> " + name + "\n"

                                raise Exception(errorMsg)
	

	except Exception as e:
		sys.exit(e)
	
if __name__ == "__main__":
	main()
