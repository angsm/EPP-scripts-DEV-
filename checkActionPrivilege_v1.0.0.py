##############################################
##SCRIPT BY  :  Ang Shimin
##CREATED    :  12 Feb 2015
##INPUT      :
##DESCRIPTION : This code checks if user changes action from manager review which is determined by QC. If
##		chanaged, an email will be sent out to all managers via GIS smtp server
##VERSION    :  1.0.0
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

SERVER = "gissmtp.gis.a-star.edu.sg"

## emailing required python modules
import smtplib
from email.mime.text import MIMEText

DEBUG = False
api = None

## BY QC
def getOutputLimsid( limsid ):
	
	inputIDArr = []
	outputIDArr = []
	
	## get current process XML
	gURI = BASE_URI + "processes/" + limsid
	gXML = api.getResourceByURI( gURI )
	gDOM = parseString( gXML )

	typeTag = gDOM.getElementsByTagName( "type" )
	type = api.getInnerXml( typeTag[0].toxml(), "type" )

	IOMaps = gDOM.getElementsByTagName( "input-output-map" )
	for IOMap in IOMaps:

		output = IOMap.getElementsByTagName( "output" )
		
		oType = output[0].getAttribute( "output-type" )
                ogType = output[0].getAttribute( "output-generation-type" )
		
		## only take artifacts
                if oType == "ResultFile" and ogType == "PerInput":
			
			## Result file
			outputLimsid = output[0].getAttribute( "limsid" )
			if outputLimsid not in outputIDArr:
				outputIDArr.append( outputLimsid )
#				print "result: " + outputIDArr[-1]	

			## Analyte
			input = IOMap.getElementsByTagName( "input" )
			inputLimsid = input[0].getAttribute( "limsid" )

			if (inputLimsid not in inputIDArr):
				inputIDArr.append(inputLimsid)
#				print "analyte: " +  inputIDArr[-1]
	
	## remove controls	
	outputIDArr, outputNodes = removeControl( outputIDArr )
	inputIDArr, inputNodes = removeControl( inputIDArr )
	
	return (outputIDArr, inputIDArr, outputNodes, inputNodes, type)

def getArtifactName( Nodes ):
	
	nameDict = {}	
	
	## collect artifact limsid and store it in dictionary
        for artifact in Nodes:
		id = artifact.getAttribute( "limsid" )
		
		nameTag = artifact.getElementsByTagName( "name" )
		name = api.getInnerXml( nameTag[0].toxml(), "name" )
		nameDict[id] = name 

	return nameDict

def removeControl( limsidArr ):
	
	## get desired excludes as list
	if "exclude" in args.keys():
		excludeArr = args[ "exclude" ].split(",")

	## Batch retrieve
        lXML = '<ri:links xmlns:ri="http://genologics.com/ri">'

        for limsid in limsidArr:
                link = '<link uri="' + BASE_URI + 'artifacts/' + limsid + '" rel="artifacts"/>'
                lXML += link
        lXML += '</ri:links>'
        gXML = api.getBatchResourceByURI( BASE_URI + "artifacts/batch/retrieve", lXML )
        gDOM = parseString( gXML )

        ## get name of artifact
        Nodes = gDOM.getElementsByTagName( "art:artifact" )

        for artifact in Nodes:
		nameTag = artifact.getElementsByTagName( "name" )
		name = api.getInnerXml( nameTag[0].toxml(), "name" )
		artID = artifact.getAttribute( "limsid" )		

		## if a partial match of excludes is in name of artifact, remove artifact from list
		for ex in excludeArr:
			isExclude = re.search( ex, name )
		
		if isExclude:
			limsidArr.remove( artID )

	## get new Nodes
	## Batch retrieve
        lXML = '<ri:links xmlns:ri="http://genologics.com/ri">'

        for limsid in limsidArr:
                link = '<link uri="' + BASE_URI + 'artifacts/' + limsid + '" rel="artifacts"/>'
                lXML += link
        lXML += '</ri:links>'
        gXML = api.getBatchResourceByURI( BASE_URI + "artifacts/batch/retrieve", lXML )
        gDOM = parseString( gXML )

	Nodes = gDOM.getElementsByTagName( "art:artifact" )

	return limsidArr, Nodes

def getQC( resultNodes, analyteNodes ):
	
	artDict = {}
	overallQCDict = {}
	count = 0	

	## Get QC flag attribute from every measurement of each sample	
        for result in resultNodes:

		## Get name
		sampleIDTag = result.getElementsByTagName( "sample" )
		sampleID = sampleIDTag[0].getAttribute( "limsid" )

		for analyte in analyteNodes:

			aSampleIDTag = analyte.getElementsByTagName( "sample" )
			aSampleID = aSampleIDTag[0].getAttribute( "limsid" )

			ID = analyte.getAttribute( "limsid" )
			
			## compare base sample ID, result file should have the same base as analyte
			isMatch = re.match( sampleID, aSampleID )
			if isMatch:
				analyteID = ID

				## Get QC value
				qcTag = result.getElementsByTagName( "qc-flag" )
				QCVal = api.getInnerXml(qcTag[0].toxml(), "qc-flag" )
		
				## Create a dictionary of list, list that contains QC for all measurements for that sample
				if not ( analyteID in artDict ):
					artDict[ analyteID ] = []
					artDict[ analyteID ].append(QCVal)
			
				else:
					artDict[ analyteID ].append(QCVal)

	## Determine overall QC
	for key in artDict:
		failCount = 0
		passCount = 0
		
		## Determine number of passes and fails within measurements of each sample
		for i in range(0, len(artDict[key])):
			if artDict[key][i].find("FAILED") > -1:
				failCount += 1
			else:
				passCount += 1		
		
		if len(artDict[key]) == failCount:
			overallQc = "FAILED"
		else:
			overallQc = "PASSED"

		overallQCDict[key] =  overallQc
	return overallQCDict

def getRole( limsid, aDOM ):
		
	roleNameArr = []

	## if escalated, get owner of step from escalation XML, else get from process XML	
	escTag = aDOM.getElementsByTagName( "escalation" )
	if escTag:
		requestTag = escTag[0].getElementsByTagName( "request" )
		authorTag = requestTag[0].getElementsByTagName( "author" )
		linkURI = authorTag[0].getAttribute( "uri" )

	else:
		## Access container limsid from process XML	
		gURI = BASE_URI + "processes/" + limsid
		gXML = api.getResourceByURI( gURI )
		gDOM = parseString( gXML )

		temp = gDOM.getElementsByTagName( "technician" )
		linkURI = temp[0].getAttribute( "uri" )

	## In researcher XML, get owner's role and name
	gXML = api.getResourceByURI( linkURI )
	gDOM = parseString ( gXML )

	Nodes = gDOM.getElementsByTagName( "role" )
	for node in Nodes:
		roleNameArr.append(node.getAttribute( "name" ))
	
	fNameTag = gDOM.getElementsByTagName( "first-name" )
	fName = api.getInnerXml( fNameTag[0].toxml(), "first-name" )

	lNameTag = gDOM.getElementsByTagName( "last-name" )
	lName = api.getInnerXml( lNameTag[0].toxml(), "last-name" )

	fullName = fName + " " + lName
	
	return roleNameArr, fullName

def getActions( limsid ):
	
	flagDict = {}
	
	## Access actiontype from action XML
        gURI = BASE_URI + "steps/" + limsid + "/actions"
        gXML = api.getResourceByURI( gURI )
        gDOM = parseString( gXML )

	Nodes = gDOM.getElementsByTagName( "next-action" )

	if Nodes > -1:
		for node in Nodes:
			## get analyet ID
			## check if artifacts' user action is complete or nextstep (illegal)
			id = (node.getAttribute( "artifact-uri" ).split("/"))[6]
			if (re.match( "complete", node.getAttribute( "action" ))) or (re.match( "nextstep", node.getAttribute( "action" ))):
				flagDict[id] = 1
			else:
				flagDict[id] = 0

	return flagDict, gDOM
	
def getEmailAdd():

	reNumArr = []
	emailArr = []	

	## Access all roles from roles XML
        gURI = BASE_URI + "roles"
        gXML = api.getResourceByURI( gURI )
        gDOM = parseString( gXML )

	roleHeader = gDOM.getElementsByTagName( "role:roles" )
	roleTag = roleHeader[0].getElementsByTagName( "role" )

	for role in roleTag:
		roleName = role.getAttribute( "name" )

		## if role is allowed, get researchers' number
		if roleName in allowedArr:
			roleURI = role.getAttribute( "uri" )
       		 	gXML = api.getResourceByURI( roleURI )
        		gDOM = parseString( gXML )

			header = gDOM.getElementsByTagName( "role:role" )
			secHeader = header[0].getElementsByTagName( "researchers" )
			researcherTag = secHeader[0].getElementsByTagName( "researcher" )

			for researcher in researcherTag:
				temp = researcher.getAttribute( "uri" ).split("/")
				if temp[6] not in reNumArr:
					reNumArr.append( temp[6] )
					#print reNumArr[-1]

	## get allowed users' email
	for num in reNumArr:
		rURI = BASE_URI + "researchers/" + str(num)
        	rXML = api.getResourceByURI( rURI )
        	rDOM = parseString( rXML )

		header = rDOM.getElementsByTagName( "res:researcher" )
		emailTag = header[0].getElementsByTagName( "email" )
		if len(emailTag) > 0:
			email = api.getInnerXml( emailTag[0].toxml(), "email" )
			
			## gissmtp server allows only .gis emails		
			if re.search( "gis" ,email):

				## python smtp requires list 
				emailArr.append(email)
	
	## change from unicode to string
        emailArr = [x.encode('UTF8') for x in emailArr]

	return emailArr

def sendEmail( smtpServer, processNum, changedArtList, researcherName, processName):
	
	## get host name
	hostname = socket.gethostname()

	emailAdd = getEmailAdd()

	## Create a text/plain message
	TEXT = "Dear Manager(s),\n"
        TEXT += "Reseacher " + researcherName + " allowed the advancement of artifact(s) which required manager review.\n\n"
	TEXT += "Process Name: " + processName + "\n"
	TEXT += "Analyte Name(s): \n"

	for art in changedArtList:
		TEXT += "-> " + art + "\n"

        TEXT += "\nThank you" + "\n\n" + "*Please do not reply, this is an automated mail*"

	## make text MIME format
	msg = MIMEText(TEXT)
	
	## for display in email
	msg['Subject'] = "Clarity LIMS unauthorized action change on " + hostname
	msg['From'] = "claritylims@gis.a-star.edu.sg"

	toArr = ",".join(emailAdd)
	msg['To'] = toArr
	print msg
	print emailAdd
	## Send the message via our own SMTP server, but don't include the envelope header
	#s = smtplib.SMTP( smtpServer )
	#s.sendmail(msg['from'], emailAdd, msg.as_string())
	#s.quit()

def getHostname():

        response = ""

        ## retrieve host name using UNIX command
        temp = socket.gethostname()
        response = "http://" + temp + ".gis.a-star.edu.sg:8080"
        
	return response

def setBASEURI( hostname ):

        global BASE_URI

        BASE_URI = hostname + "/api/" + VERSION + "/"

def main():

	global api
	global args
	args = {}

	global allowedArr
	currRoles = []
	nameList = []
	roleAcceptedCount = 0
	deniedCount = 0
	
	allowedArr = []

	opts, extraparams = getopt.getopt(sys.argv[1:], "u:p:l:x:", ["rolesAllowed="])
	for o,p in opts:
		if o == '-u':
			args[ "username" ] = p
		elif o == '-p':
			args[ "password" ] = p
		elif o == '-l':
			args[ "processID" ] = p
		elif o == '--rolesAllowed':
			allowedArr = p.split(",")
		elif o == '-x':
			args[ "exclude" ] = p		
	
	HOSTNAME = getHostname()
	setBASEURI(HOSTNAME)
	
	api = glsapiutil.glsapiutil()
	api.setHostname( HOSTNAME )
	api.setVersion( VERSION )
	api.setup( args[ "username" ], args[ "password" ] )

	## Get process's next actions
	isCompleteDict, aDOM = getActions( args[ "processID" ] )

	## Get user's assigned roles
        currRoles, rName = getRole( args[ "processID" ], aDOM )

	## Get artifact data
	resultIDArr, analyteIDArr, resultNodes, analyteNodes, pName = getOutputLimsid( args[ "processID" ] )

	## Get names of analyte
        analyteNameDict = getArtifactName( analyteNodes )

	## Overall QC for each analyte with many measurements
	overallDict = getQC( resultNodes, analyteNodes )

	## Only have to take note of samples that have a overall failed QC and where the user selects "complete" action
	for i in range(0, len(analyteIDArr)):
		if (overallDict[analyteIDArr[i]] == "FAILED") and (isCompleteDict[analyteIDArr[i]] == 1):
			deniedCount += 1

			## Storing the names for listing
			nameList.append( analyteNameDict[analyteIDArr[i]] )
		
	## Check if user's assigned roles are within specified roles in script, parameter -r
	for allowed in allowedArr:
		if allowed in currRoles:
			roleAcceptedCount += 1
	
	## if user's role is accepted and manager review action changed is less than 0
	#if ( roleAcceptedCount < 1 ) and ( deniedCount > 0 ):
	processNum = (re.search("\d+\-(\d+)", args["processID"])).group(1)
	sendEmail( SERVER, processNum, nameList, rName, pName)

if __name__ == "__main__":
	main()
