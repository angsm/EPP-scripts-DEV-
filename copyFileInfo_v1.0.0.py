##############################################
##SCRIPT BY  :  Ang Shimin
##CREATED    :  04 MAR 2015
##INPUT      :
##DESCRIPTION : Script searches for links for file attached to reagent labels in prev step as indicated
##		by parameter --prevProcess and attach it in UDF "Current Report". 
##		When ranking is needed, --prevProcess <rank 1>,<rank 2>
##P_VERSION    :  1.0.0
##############################################

import socket
import sys
from datetime import datetime as dt
import getopt
import glsapiutil
import re
from xml.dom.minidom import parseString
import HTMLParser
import difflib

#HOST='dlap73v.gis.a-star.edu.sg'
#HOSTNAME = 'http://'+HOST+':8080'
VERSION = "v2"
BASE_URI = ""

DEBUG = False
api = None

def getPrevPID():
	
	artIDs = []
	IDArr = []
	parentIDs = []
	isFound = 0
	
	## get analyte limsid from actions xml	
	sURI = BASE_URI + "steps/" + args[ "processID" ] + "/actions"
        sXML = api.getResourceByURI( sURI )
        sDOM = parseString( sXML )

	actionTag = sDOM.getElementsByTagName( "next-action" )
	for tag in actionTag:
		artID = (tag.getAttribute( "artifact-uri" )).split("/")
		artIDs.append(artID[6])

	for ID in artIDs:
		## search through the history of analyte
		pURI = BASE_URI + "processes/" + "?inputartifactlimsid=" + ID
        	pXML = api.getResourceByURI( pURI )
        	pDOM = parseString( pXML )
		
		## this artifact is done, break and go to next artifact
                if isFound == 1:
			isFound = 0
                	break

		## past processes that the artifact had gone through
		pTag = pDOM.getElementsByTagName( "process" )
		for p in reversed(pTag):
			pID = p.getAttribute( "limsid" )
			pURI = BASE_URI + "processes/" + pID
	                pXML = api.getResourceByURI( pURI )
        	        pDOM = parseString( pXML )
			
			typeTag = pDOM.getElementsByTagName( "type" )
			type = api.getInnerXml( typeTag[0].toxml(), "type" )

			## remove html code (i.e. amp;) from type variable
                        h = HTMLParser.HTMLParser()
			
			## will split prevProcess parameter if there are commas
			lastProcess = args[ "process" ].split( "," )
			
			## will try to match desired prevProcess from front, if found, break loop
			for process in lastProcess:
				if (difflib.SequenceMatcher(None, h.unescape(type), process).ratio()) * 100 > 90:
                        	#if h.unescape(type) ==  process:
					## check if processID is not duplicated and not current process
					if pID not in IDArr and pID != args[ "processID" ]:
						IDArr.append( pID )
						isFound = 1
					break
		
		## if duplicates of the same process exist, take the latest one
		parentID = sorted( IDArr, reverse=True)[0]
		if parentID not in parentIDs:
			parentIDs.append(parentID)

	return parentIDs

def getArtifacts( processID ):
	
	artIDs = []
	
	## get artifacts from process xml
	pURI = BASE_URI + "processes/" + processID
        pXML = api.getResourceByURI( pURI )
        pDOM = parseString( pXML )

        outputTag = pDOM.getElementsByTagName( "output" )

	## search for reagents labels in the tube
        for output in outputTag:
                genType = output.getAttribute( "output-generation-type" )
                outputType = output.getAttribute( "output-type" )

                if genType == "PerReagentLabel" and outputType == "ResultFile":
                        artIDs.append(output.getAttribute( "limsid" ))	

	## Batch retrieve artifacts
	lXML = '<ri:links xmlns:ri="http://genologics.com/ri">'
	
	for limsid in artIDs:
                link = '<link uri="' + BASE_URI + 'artifacts/' + limsid + '" rel="artifacts"/>'
                lXML += link
        lXML += '</ri:links>'
        gXML = api.getBatchResourceByURI( BASE_URI + "artifacts/batch/retrieve", lXML )
        gDOM = parseString( gXML )	
	
	## get nodes by determining artifact from tag
	nodes = gDOM.getElementsByTagName( "art:artifact" )
	
	return nodes

def getArtID():

	currArtIDs = []
	
	## get artifact nodes
	artNodes = getArtifacts( args[ "processID" ] )

	## collect and store current step artifacts' limsid
	for artifact in artNodes:
		id = artifact.getAttribute( "limsid" )

                currArtIDs.append(id)

        return currArtIDs

def getFileURI():

	artFileDict = {}
	artRemark = {}

	prevProcessIDs = getPrevPID()
	for pPID in prevProcessIDs:
		artNodes = getArtifacts( pPID )

		for artifact in artNodes:
			## get name of artifact for identifications later
                	nameTag = artifact.getElementsByTagName( "name" )
                	name = api.getInnerXml( nameTag[0].toxml(), "name" )
			
			## get current report link			
                	fileTag = artifact.getElementsByTagName( "file:file" )
			
			## get current report remark if available
			remark = api.getUDF( artifact, "New Report Remark" )
			
			if not remark:
				remark = api.getUDF( artifact, "Current Report Remark" )
			
			if remark:	
				artRemark[name] = remark

			## get file limsid and form the link if file tag exist
                	if fileTag:
                		fileID = (fileTag[0].getAttribute( "limsid" ).split("-"))[1]
                        	artFileDict[name] = HOSTNAME + "/clarity/api/files/" + fileID
	return artFileDict, artRemark
	
def setFileURI( fileDict, remarkDict, IDArr ):

	for id in IDArr:

		aURI = BASE_URI + "artifacts/" + id
	        aXML = api.getResourceByURI( aURI )
        	aDOM = parseString( aXML )

		currNameTag = aDOM.getElementsByTagName( "name" )
		currName = api.getInnerXml( currNameTag[0].toxml(), "name" )
		
		## get file link using current artifact name as a key of the dictionary
		if currName in fileDict:
			#print currName + " : " + fileDict[ currName ]
			api.setUDF( aDOM, "Current Report", fileDict[ currName ] )
			
		if currName in remarkDict and remarkDict:
			api.setUDF( aDOM, "Current Report Remark", remarkDict[ currName ] )	

		response = api.updateObject( aDOM.toxml(), aURI )
		#print response

def copyFile( fileDict, remarkDict, IDArr ):
	
	## check if artifacts have empty UDFs, if yes, fill it up with current UDF values
	for id in IDArr:
		
		contentLoc = ""
	        attachedto = ""
        	originalLoc = ""

        	aURI = BASE_URI + "artifacts/" + id
                aXML = api.getResourceByURI( aURI )
                aDOM = parseString( aXML )

                currNameTag = aDOM.getElementsByTagName( "name" )
                currName = api.getInnerXml( currNameTag[0].toxml(), "name" )
	
		## check if file placeholder is empty, if empty, fill it up with current file	
		gotFile = aDOM.getElementsByTagName( "file:file" )
		if (currName in fileDict) and (not gotFile):

			## get file details
			fURI = BASE_URI + "files/40-" + (fileDict[ currName ].split("/"))[6]
	                fXML = api.getResourceByURI( fURI )
        	        fDOM = parseString( fXML )

			contentLocTag = fDOM.getElementsByTagName( "content-location" ) 
			contentLoc = api.getInnerXml( contentLocTag[0].toxml(), "content-location" )	
			
			originalLocTag = fDOM.getElementsByTagName( "original-location" )
                        originalLoc = api.getInnerXml( originalLocTag[0].toxml(), "original-location" )			
			attachedto = BASE_URI + "artifacts/" + id

			xml ='<?xml version="1.0" encoding="UTF-8"?>'
	                xml += '<file:file xmlns:file="http://genologics.com/ri/file">'
        	        xml += '<content-location>' + contentLoc  + '</content-location>'
                	xml += '<attached-to>' + attachedto  + '</attached-to>'
                	xml += '<original-location>' + originalLoc  + '</original-location>'
                	xml += '</file:file>'

        	        response = api.createObject( xml, BASE_URI + "files" )
	
                	#print response
		
		## check if remark is empty, if empty, fill it up with current remark
		if args[ "stepNum" ] == "1" or args[ "stepNum" ] == "3" and remarkDict:

			gotNewRemark = api.getUDF( aDOM, "New Report Remark" )
        	        if (currName in remarkDict) and (not gotNewRemark):

				currRemark = api.getUDF( aDOM, "Current Report Remark" )

	                        api.setUDF( aDOM, "New Report Remark", currRemark )

        	        	response = api.updateObject( aDOM.toxml(), aURI )

def getHostname():

        response = ""

        ## retrieve host name using UNIX command
        temp = socket.gethostname()
        response = "http://" + temp + ".gis.a-star.edu.sg:8080"
        
	return response

def setBASEURI(hostname):
       
	global BASE_URI

        BASE_URI = hostname + "/api/" + VERSION + "/"

def main():

	global api
	global args

	global HOSTNAME
	
	args = {}

	opts, extraparams = getopt.getopt(sys.argv[1:], "u:p:l:", ["prevProcess=","mode=","stepNumber=","checkUDF=","UDFRunVal="])
	for o,p in opts:
		if o == '-u':
			args[ "username" ] = p
		elif o == '-p':
			args[ "password" ] = p
		elif o == '-l':
			args[ "processID" ] = p

		elif o == '--prevProcess':
			args[ "process" ] = p
		elif o == '--mode':
			args[ "fileMode" ] = p	
		elif o == '--stepNumber':
			args[ "stepNum" ] = p
		
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
		pURI = BASE_URI + "processes/" + args[ "processID" ]
	        pXML = api.getResourceByURI( pURI )
        	pDOM = parseString( pXML )

		UDFInput = api.getUDF( pDOM, args[ "UDF" ] )
		if not UDFInput == args[ "UDFVal" ]:
			exit()

	fileDict, remarkDict = getFileURI()
	artIDArr = getArtID()

	if args[ "fileMode" ] == "get":
		setFileURI( fileDict, remarkDict, artIDArr )
	
	elif args[ "fileMode" ] == "set":
		copyFile( fileDict, remarkDict, artIDArr )
	
	else:
		print "Script mode is not set"

if __name__ == "__main__":
	main()
