#############################################
##SCRIPT BY  :  Ang Shimin
##CREATED    :  25 Feb 2015
##INPUT      :
##DESCRIPTION : Script takes in parameter --processName and pushes analytes to that specific step
##		--reworkBoolUDF takes in name of checkbox UDF and -x takes in name of artifact that is
##		to be excluded from the script's action
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
import os

#HOST='dlap73v.gis.a-star.edu.sg'
#HOSTNAME = 'http://'+HOST+':8080'
VERSION = "v2"
BASE_URI = ""

DEBUG = False
api = None

def getAnalyteID():
	
	inputIDs = []
	global isRework	

	## get analyte ID from the current process
	pURI = BASE_URI + "processes/" + args[ "processID" ]
        pXML = api.getResourceByURI( pURI )
	pDOM = parseString( pXML )

	## check if rework is step is base on UDF checkbox
	if "reworkUDF" in args.keys():
		isRework = api.getUDF( pDOM, args[ "reworkUDF" ] )
		print "Rework? : " + isRework

	IOMaps = pDOM.getElementsByTagName( "input-output-map" )

	for IOMap in IOMaps:
		inputTag = IOMap.getElementsByTagName( "input" )
		inputLimsid = inputTag[0].getAttribute( "limsid" )

		if inputLimsid not in inputIDs:		
			inputIDs.append( inputLimsid )
	
	if "exclude" in args.keys():
		inputIDs = removeControls(inputIDs)

	return inputIDs

def removeControls( artIDs ):
	
	## batch collect artifacts
	lXML = '<ri:links xmlns:ri="http://genologics.com/ri">'

        for limsid in artIDs:
                link = '<link uri="' + BASE_URI + 'artifacts/' + limsid + '" rel="artifacts"/>'
                lXML += link
        lXML += '</ri:links>'

        mXML = api.getBatchResourceByURI( BASE_URI + "artifacts/batch/retrieve", lXML )
        mDOM = parseString( mXML )
        nodes = mDOM.getElementsByTagName( "art:artifact" )

	## comma seperated string to list
	excludeArr = args[ "exclude" ].split(",")
	
	## check artifacts if their names are in the exclude list
        for artifact in nodes:
		nameTag = artifact.getElementsByTagName( "name" )
		name = api.getInnerXml( nameTag[0].toxml(), "name" )
		
		id = artifact.getAttribute( "limsid" )
		
		## remove artifact limsid from list	
		if re.search(exclude, name):
			artIDs.remove( id )

	return artIDs

def getPrevStepURI( artIDs ):

	artDetailsDict = {}
	PIDArr = []
	
	for id in artIDs:
		## get rework-step-URI
		oURI = BASE_URI + "processes?inputartifactlimsid=" + id
		oXML = api.getResourceByURI( oURI )
		oDOM = parseString( oXML )

		pTag = oDOM.getElementsByTagName( "process" )
		for p in pTag:
			pURI = BASE_URI + "processes/" + p.getAttribute( "limsid" )
			pXML = api.getResourceByURI( pURI )
			pDOM = parseString( pXML )
			typeTag = pDOM.getElementsByTagName( "type" )			
			type = api.getInnerXml(typeTag[0].toxml(), "type" )
			
			## remove html code (i.e. amp;) from type variable	
			h = HTMLParser.HTMLParser()
			if h.unescape(type) == args[ "process" ] and p.getAttribute( "limsid" ) != args[ "processID" ]:
				processTag = pDOM.getElementsByTagName( "prc:process" )
				PIDArr.append(processTag[0].getAttribute( "limsid" ))
		
		if len(PIDArr) > 0:
			## if match multiple past processes, take the latest one
			prevPID = sorted(PIDArr, reverse=True)[0]

			## get stepURI
			sURI = BASE_URI + "steps/" + prevPID
                	sXML = api.getResourceByURI( sURI )
                	sDOM = parseString( sXML )

			conTag = sDOM.getElementsByTagName( "configuration" )
			conURI = conTag[0].getAttribute( "uri" )
		
			if id not in artDetailsDict:
				artDetailsDict[id] = {}
			artDetailsDict[id][0] = BASE_URI + "steps/" + prevPID
			artDetailsDict[id][1] = conURI

		PIDArr = []		
	
	return artDetailsDict
		
def getTransitURI():
	
	response = ""
	
	## get step configuration
	stepXML = api.getResourceByURI( args[ "stepURI" ] )
	stepDOM = parseString( stepXML )
	nodes = stepDOM.getElementsByTagName( "configuration" )
	if nodes:
		cfXML = nodes[0].toxml()

	## get transition action URI
	DOM = parseString( cfXML )
	nodes = DOM.getElementsByTagName( "configuration" )
	if nodes:
		cfURI = nodes[0].getAttribute( "uri" )
		stXML = api.getResourceByURI( cfURI )
		stDOM = parseString( stXML )
		nodes = stDOM.getElementsByTagName( "transition" )
		if nodes:
			naURI = nodes[0].getAttribute( "next-step-uri" )
			response = naURI

	return response

def setAction( artDetails, artIDs ):

	## get existing actions from current step	
	aURI = args[ "stepURI" ] + "/actions"
	aXML = api.getResourceByURI( aURI )
	aDOM = parseString( aXML )
	
	## set rework attributes, actions, rework step uri and step uri
	nodes = aDOM.getElementsByTagName( "next-action" )
	for node in nodes:
		
		artURI = (node.getAttribute( "artifact-uri" )).split("/")

		## is rework UDF bool is true, set rework attributes onto artifact node
		if isRework == args["UDFVal"]:
			if artURI[6] in artDetails:
				node.setAttribute( "action", "rework" )
				node.setAttribute( "step-uri", artDetails[artURI[6]][1] )
				node.setAttribute( "rework-step-uri", artDetails[artURI[6]][0] )

		else:
			## direct artifact to next step or complete protocol where appropriate
			## next step if transition URI is available
			if artDetails:
				node.setAttribute( "action", "nextstep")
				node.setAttribute( "step-uri", artDetails )

				if node.hasAttribute( "rework-step-uri" ):
					node.removeAttribute( "rework-step-uri" )
			else:
				node.setAttribute( "action", "complete" )
				
				if node.hasAttribute( "step-uri" ):
					node.removeAttribute( "step-uri" )
				if node.hasAttribute( "rework-step-uri" ):
                                	node.removeAttribute( "rework-step-uri" )

	#print aDOM.toxml()	
	rXML = api.updateObject( aDOM.toxml(), args[ "stepURI" ] + "/actions" )

	#print rXML	

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

	global SERVER	

	args = {}

	containerIDs = []

	opts, extraparams = getopt.getopt(sys.argv[1:], "u:p:l:s:x:", ["processName=", "reworkBoolUDF=", "UDFValue="])
	for o,p in opts:
		if o == '-u':
			args[ "username" ] = p
		elif o == '-p':
			args[ "password" ] = p
		elif o == '-l':
			args[ "processID" ] = p
		elif o == '-s':
			args[ "stepURI" ] = p
		
		elif o == '--processName':
			args[ "process" ] = p
		elif o == '-x':
			args[ "exclude" ] = p
		
		## rework UDF parameters, if match value, script will rework
		elif o == '--reworkBoolUDF':
			args[ "reworkUDF" ] = p
		elif o == '--UDFValue':
			args[ "UDFVal" ] = p

	HOSTNAME = getHostname()
	setBASEURI(HOSTNAME)	
	
	api = glsapiutil.glsapiutil()
	api.setHostname( HOSTNAME )
	api.setVersion( VERSION )
	api.setup( args[ "username" ], args[ "password" ] )
	
	## get input analyte IDs
	inputIDArr = getAnalyteID()

	## check if rework UDF is true, get process URI from last step, else, get process URI of next step
	if isRework == args[ "UDFVal" ]:
		stepURIs = getPrevStepURI( inputIDArr )
	else:
		stepURIs = getTransitURI()
	
	setAction( stepURIs, inputIDArr )

if __name__ == "__main__":
	main()
