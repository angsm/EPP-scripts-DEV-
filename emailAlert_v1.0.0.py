##############################################
##SCRIPT BY  :  Ang Shimin
##CREATED    :  10 Feb 2015
##INPUT      :
##DESCRIPTION : Script email process owner or sepecified email address using parameter, uses optional
##		parameters of --techName, --techNum, --emailAddress for recipient specification. Else
##		script will search for owner of the process/step. --prevProcess takes in process name
##		in which the link in the mail will point to it. --reworkItem will trigger the rework
##		message
##D_VERSION    :  1.0.0
##############################################

import socket
import sys
from datetime import datetime as dt
import getopt
import glsapiutil
import re
from xml.dom.minidom import parseString
import HTMLParser
from collections import defaultdict

## emailing required python modules
import smtplib
from email.mime.text import MIMEText

#HOST='dlap73v.gis.a-star.edu.sg'
#HOSTNAME = 'http://'+HOST+':8080'
VERSION = "v2"
BASE_URI = ""

DEBUG = False
api = None

SERVER = "gissmtp.gis.a-star.edu.sg"

def getPrevPID( processStr ):
	
	artIDs = []
	IDArr = []
	parentIDs = []
	isFound = 0	
	
	## get analyte limsid from action xml
	sURI = BASE_URI + "steps/" + args[ "processID" ] + "/actions"
        sXML = api.getResourceByURI( sURI )
        sDOM = parseString( sXML )

	actionTag = sDOM.getElementsByTagName( "next-action" )
	for tag in actionTag:
		artID = (tag.getAttribute( "artifact-uri" )).split("/")
		artIDs.append(artID[6])

	## use http query to get the processes that each artifact is involved in
	for ID in artIDs:

		if isFound == 1:
                        isFound = 0
                        break

		pURI = BASE_URI + "processes/" + "?inputartifactlimsid=" + ID
        	pXML = api.getResourceByURI( pURI )
        	pDOM = parseString( pXML )
		
		## look through each past process for match
		pTag = pDOM.getElementsByTagName( "process" )
		for p in pTag:
			pID = p.getAttribute( "limsid" )
			pURI = BASE_URI + "processes/" + pID
	                pXML = api.getResourceByURI( pURI )
        	        pDOM = parseString( pXML )
			
			typeTag = pDOM.getElementsByTagName( "type" )
			type = api.getInnerXml( typeTag[0].toxml(), "type" )
			
			## remove html code (i.e. amp;) from type variable
                        h = HTMLParser.HTMLParser()

			## will split prevProcess parameter if there are commas
                        lastProcess = processStr.split( "," )
			
			## will try to match desired prevProcess from front, if found, break loop
			for process in lastProcess:
				if (difflib.SequenceMatcher(None, h.unescape(type), process).ratio()) * 100 > 90:

                        	#if h.unescape(type) == process:
					p = (pID).split("-")

					## check if processID is not duplicated and not current process
					if p[1] not in IDArr and pID != args[ "processID" ]:
						IDArr.append( p[1] )
						isFound = 1
						break

		
		## for each artifact, if there is multiple qualifying process id, take the latest 
		parentID = sorted( IDArr, reverse=True)[0]
		if parentID not in parentIDs:
			parentIDs.append(parentID)
	
	return parentIDs,pDOM

def searchForTech():
	
	techURI = []
	
	## if optional parameter --techName is used, search for technician name in xml
	if "name" in args.keys():
		
		nameArr = args[ "name" ].split(",")
			
		## get technician nodes
	        gURI = BASE_URI + "researchers"
        	gXML = api.getResourceByURI( gURI )
        	gDOM = parseString( gXML )
		
		researcherTag = gDOM.getElementsByTagName( "res:researchers" )	
		techList = researcherTag[0].getElementsByTagName( "researcher" )

		for tech in techList:
			fNameTag = tech.getElementsByTagName( "first-name" )
			fName = api.getInnerXml( fNameTag[0].toxml(), "first-name" )

			lNameTag = tech.getElementsByTagName( "last-name" )
                        lName = api.getInnerXml( lNameTag[0].toxml(), "last-name" )
			
			fullName = fName + lName
			## search for match of pattern anywhere in the string
			for name in nameArr:
				if fullName.lower().find( name.lower() ) > -1:
        				techURI.append(tech.getAttribute( "uri" ))

	## if optional parameter --techNum is entered, append technician number in url
	elif "number" in args.keys():
		number = args[ "number" ].split(",")

		for num in number:
			URI = BASE_URI + "researchers/" + num
			techURI.append(URI)
	
	## if optional parameter --roleName is entered, get all tech emails base on roles
	elif "role" in args.keys():
		
		wantedRolesURI = []
		rList = args[ "role" ].split(",")

		## match role names
		roURI = BASE_URI + "roles"
                roXML = api.getResourceByURI( roURI )
                roDOM = parseString( roXML )

		roleTag = roDOM.getElementsByTagName( "role" )
		for role in roleTag:
			roleName = role.getAttribute( "name" )
			for r in rList:
				if re.match( roleName.lower(), r.lower()):
					wantedRolesURI.append( role.getAttribute( "uri" ))

		## get researcher URIs base on role
		for uri in wantedRolesURI:
                	rXML = api.getResourceByURI( uri )
               		rDOM = parseString( rXML )

			researcherTag = rDOM.getElementsByTagName( "researcher" )	
			for researcher in researcherTag:
				rURI = researcher.getAttribute( "uri" )
				if rURI not in techURI:
					techURI.append( rURI )

	else:
		pPIDs = []
		if "prevTech" in args.keys():
			pPIDs, pDOM = getPrevPID( args[ "prevTech" ] )
			
			## concat a 24- in front of process id using list comprehension
			pPIDs = [( "24-" + str) for str in pPIDs ]
		else:
			pPIDs.append( args[ "processID" ] )
		
		## pPIDs contains process id in format 24-xxxxx
		for id in pPIDs:
			## search process xml for technician details
	        	gURI = BASE_URI + "processes/" + id
        		gXML = api.getResourceByURI( gURI )
	        	gDOM = parseString( gXML )

        		techTag = gDOM.getElementsByTagName( "technician" )
        		techURI.append( techTag[0].getAttribute( "uri" ))

	return techURI

def getTechEmail():
	
	emailAdd = []

	## get technician xml uri link
	techURI = searchForTech()
	## get technician data
	for URI in techURI:
        	tXML = api.getResourceByURI( URI )
        	tDOM = parseString( tXML )
	
		## get email address from xml
		tech = tDOM.getElementsByTagName( "res:researcher" )
		emailAddTag = tech[0].getElementsByTagName( "email" )
		email = api.getInnerXml( emailAddTag[0].toxml(), "email" )		

		if emailAddTag and re.search( "gis" ,email):
			emailAdd.append( email )
		
	return emailAdd

def getArtNames( processID ):

	artIDDict = defaultdict(list)
	artIDs = []
	artNameMap = {}

	## retrieve inputs and their outputs
	pURI = BASE_URI + "processes/" + processID
        pXML = api.getResourceByURI( pURI )
        pDOM = parseString( pXML )

        IOMaps = pDOM.getElementsByTagName( "input-output-map" )
        for IOMap in IOMaps:
		outputTag = IOMap.getElementsByTagName( "output" )
		ogtype = outputTag[0].getAttribute( "output-generation-type" )
        	if ogtype == "PerInput" or ogtype == "PerReagentLabel":
                	outputID = outputTag[0].getAttribute( "limsid" )
		
			inputTag = IOMap.getElementsByTagName( "input" )
			inputID = inputTag[0].getAttribute( "limsid" )
			if inputID not in artIDDict:
				artIDDict[inputID] = []
			artIDDict[inputID].append( outputID )
			
			## create a list of limsid for name retrieving in the next step
			if outputID not in artIDs:
				artIDs.append( outputID )
			if inputID not in artIDs:
				artIDs.append( inputID )	

	## Batch retrieve input/output artifacts names and limsid for matching later
        lXML = '<ri:links xmlns:ri="http://genologics.com/ri">'

        for limsid in artIDs:
                link = '<link uri="' + BASE_URI + 'artifacts/' + limsid + '" rel="artifacts"/>'
                lXML += link
        lXML += '</ri:links>'
        gXML = api.getBatchResourceByURI( BASE_URI + "artifacts/batch/retrieve", lXML )
        gDOM = parseString( gXML )

        ## get name
        nodes = gDOM.getElementsByTagName( "art:artifact" )
	
	for node in nodes:
		id = node.getAttribute( "limsid" )

		nameTag = node.getElementsByTagName( "name" )
		name = api.getInnerXml( nameTag[0].toxml(), "name" )
	
		artNameMap[id] = name
	return artIDDict, artNameMap

def sendEmail( smtpServer, emailAdd, usrSub):

	## Create a text/plain message
	TEXT = "Dear User,\n"
        TEXT += "A step in Clarity LIMS requires your attention for " + usrSub + "\n\n"

	IDDict, NameMap = getArtNames( args[ "processID" ] )
	
	## email if rework UDF is true, different message
	if "rework" in args.keys():
		
		reworkStr = args[ "rework" ].split( "::" )
		item = reworkStr[0]
		step = reworkStr[1]

		TEXT += "This is an email to notify that there are incorrect " + item  + " in the current step, therefore there will be a rollback to step '" + step  +  "' to retify the data.\n"

		TEXT += "\nArtifacts reworked:"

	else:
		## everything else that is not rewok, provides link to current step
		HOST = getHostname()
		if re.search( "signature", args[ "subject" ].lower() ):
        		TEXT += "Link: " + HOST  + "/clarity/work-details/" + args[ "processNumber" ] + "\n"
		else:
			TEXT += "Link: " + HOST  + "/clarity/work-complete/" + args[ "processNumber" ] + "\n"

		TEXT += "\nArtifacts involved:"
	
	## artifact names from current process the script is triggered at
	for key in IDDict:
		TEXT += "\n" + NameMap[key] + "\n"
		for item in IDDict[key]:
			TEXT += "->" + NameMap[item] + "\n"

		TEXT += "\n"

	TEXT += "Thank you" + "\n\n" + "*This is an automated mail, please do not reply to this mail*"
	
	## make text MIME format
	msg = MIMEText(TEXT)
	#print msg	

	## for displaying only
	msg['Subject'] = "Clarity LIMS " + usrSub
	msg['From'] = "claritylims@gis.a-star.edu.sg"

	## list to string, check if its a string first
	toArr = ",".join(emailAdd)
	msg['To'] = toArr
	
	## real address that sendmail module use shld be a list
	## Send the message via our own SMTP server, but don't include the envelope header
	s = smtplib.SMTP( smtpServer )
	s.sendmail(msg['from'], emailAdd, msg.as_string())
	s.quit()

def getHostname():

        response = ""

        ## retrieve host name using UNIX command
        temp = socket.gethostname()
        response = "http://" + temp + ".gis.a-star.edu.sg:8080"
        
	return response

def setBASEURI(hostname):
       
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

	global SERVER	

	args = {}

	containerIDs = []

	opts, extraparams = getopt.getopt(sys.argv[1:], "u:p:l:s:", ["msgSub=","techName=", "techNum=", "emailAddress=","emailRole=","prevStepTech=","reworkItem=","UDFName=","UDFValue="])
	for o,p in opts:
		if o == '-u':
			args[ "username" ] = p
		elif o == '-p':
			args[ "password" ] = p
		elif o == '-l':
			args[ "processID" ] = p

			## extract the back digits
			args[ "processNumber" ] = (re.search("\d+\-(\d+)", args["processID"])).group(1)
		elif o == '-s':
			args[ "stepURI" ] = p
		elif o == '--msgSub':
                        args[ "subject" ] = p
		
		## optional parameter to find emails
		elif o == '--techName':
			args[ "name" ] = p
		elif o == '--techNum':
			args[ "number" ] = p
		elif o == '--emailAddress':
			args[ "email" ] = p
		elif o == '--emailRole':
			args[ "role" ] = p
		elif o == '--prevStepTech':
			args[ "prevTech" ] = p

		## optional step related parameters
		elif o == '--reworkItem':
			args[ "rework" ] = p
		elif o == '--UDFName':
			args[ "UDF" ] = p
		elif o == '--UDFValue':
			args[ "UDFVal" ] = p
	
	HOSTNAME = getHostname()
	setBASEURI(HOSTNAME)	
	
	api = glsapiutil.glsapiutil()
	api.setHostname( HOSTNAME )
	api.setVersion( VERSION )
	api.setup( args[ "username" ], args[ "password" ] )

	## check whether
	if "UDF" in args.keys():
		checkRunUDF()
	
	## if optional parameter --emailAddress is used, don't search, just use it	
	if "email" in args.keys():
        	emailAdd = args[ "email" ].split(",")
		
		## check if any other email function is activated, thus more email add
		if any(x in args.keys() for x in ['name','number','role','prevTech']):
			emailAdd.extend( getTechEmail() )

        	        ## change from unicode to string, remove duplicates (i.e. list(set(t)) )
	                emailAdd = list(set([x.encode('UTF8') for x in emailAdd]))
	else:
		emailAdd = getTechEmail()
		
		## change from unicode to string
		emailAdd = [x.encode('UTF8') for x in emailAdd]
	
	try:
		sendEmail( SERVER, emailAdd, args[ "subject" ])


	
	## recipient error	
	except smtplib.SMTPRecipientsRefused:
		response = "Recipient email address provided cannot be sent by GIS SMTP server, you might want email the recipient personally"
		api.reportScriptStatus( args[ "stepURI" ], "WARN", response )
	
	## other SMTP error
	except smtplib.SMTPResponseException as e:
		response = "An error has occurred, please contact the LIMS administrator team. /n Error code: " + e.smtp_code
		sys.exit(response)	

if __name__ == "__main__":
	main()
