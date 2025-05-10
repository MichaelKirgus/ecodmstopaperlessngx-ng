from xml.dom import minidom
import pathlib
from pprint import pprint
import requests
from requests.auth import HTTPBasicAuth
import logging
import http.client as http_client
import errno
from socket import error as socket_error
import json
import time
from datetime import datetime
import argparse
import re
import mimetypes

# To use this script, create an export in ecodms (version 18.09 in my case) with a search string
# like "docid >= 0". This will export all of your documents in a zip file with an xml-file "export.xml"

# Where is your ecodms export saved?
ecodmsfolder = "<Path to you ecoDMS export folder>"
archiveFolder = ecodmsfolder + "/archive/"
exportXMLFile = archiveFolder + "export.xml"

# Configure your paperless URL and credentials
paperlessurl = "<URL to your paperless-ngx instance>:8000"
paperlessuser = "<user for token auth in paperless-ngx>"
paperlesspassword = "<password for user in paperless-ngx (if no token used)>"
paperlesscert = False #Set to False if no ssl verification is needed, true if "real" cert is used or path to a cert for manual check
# Use preconfigured token (if not set, try to get token from API)
paperlesstoken = "<Token for user in paperless-ngx>"
# Empty authorization header var for later use
headers_token = ""

# Filetypes that can be put into paperless directly - in this case the original file instead of 
# the pdf representation is chosen. Please update to your needs
supportedFiletyped = [".pdf", ".jpg", ".tif", ".odt", ".odp", ".ods", ".docx", ".doc", ".txt", ".ppt", ".pptx", ".xls", ".xlsx"]

# Important for big data migrations: To improve performance, use this to run multiple instances of the script to import into paperless
# Use the command args ---start and --end to set the import range for each instance, e.g. 0-1000,1001-2000...
# Import range (start)
start_index = 0
# Import to document count in XML DOM (-1 to import to end)
end_Index = -1
# Blacklisted ecoDMS-IDs that should not imported (set this to -1 to disable)
blacklisted_ids = [-1]
# Retry connection is connection is refused at task API endpoint
retry_task_api = bool(True)
# Ignore errors and skipping documents, if there are errors at the file post (file duplicate)
skip_documents = bool(True)
# Ignore errors if there are errors at bulk edit an document after adding it (unknown fields, too long data)
skip_bulk_errors = bool(True)
# Ignore errors if the document owner can not altered
skip_owner_errors = bool(True)
# Update documents already imported in paperless (extract related document ID from error response)
alter_duplicate_documents = bool(True)

# Additional options
# Add note with raw XML hive to each document
add_note_xml = bool(True)
# Add custom fields and set them in paperless
add_custom_fields = bool(True)
# Set document owner (user)
alter_document_owner = bool(True)
# Time between task API polling
task_api_polling_interval = float(0.5)
# Additional time if an connection was refused (rate-limiting)
task_api_polling_refused_sleep = float(5)

# You must initialize logging, otherwise you'll not see debug output.
logging.basicConfig()
logging.getLogger().setLevel(logging.DEBUG)
requests_log = logging.getLogger("requests.packages.urllib3")
requests_log.setLevel(logging.DEBUG)
requests_log.propagate = True

#http_client.HTTPConnection.debuglevel = 1 # Full Request logging

# TODO: recognized if a file is "trashed" (atm even the trashed files are being imported)

def getVersionMetadata(version):
    tags = []
    correspondent = ""
    created = ""
    revision= ""
    letzte_aenderung = ""
    bemerkung = ""
    ordner = ""
    hauptordner = ""
    status = ""
    erhaltenerstellt = ""
    bezahlt_am = ""
    empfänger = ""
    bestellnummer = ""
    kundennummer = ""
    betragsumme = ""
    iban = ""
    rechnungsnummer = ""
    auftragsnummer = ""
    bestellung_vom = ""
    unterzeichnet_von = ""
    unterzeichnet_am = ""
    produkt = ""
    sprache = ""
    dokumentenart = ""
    dateinameOrig = ""
    dateiname = ""
    try:
        if version.getElementsByTagName('status')[0].firstChild.nodeValue not in tags:
            tags.append(version.getElementsByTagName('status')[0].firstChild.nodeValue[:127])
    except:
        pass
    try:
        if version.getElementsByTagName('revision')[0].firstChild.nodeValue not in tags:
            tags.append(version.getElementsByTagName('revision')[0].firstChild.nodeValue)
    except:
        pass
    try:
        if version.getElementsByTagName('iban')[0].firstChild.nodeValue not in tags:
            tags.append(version.getElementsByTagName('iban')[0].firstChild.nodeValue[:127])
    except:
        pass
    try:
        if version.getElementsByTagName('empfänger')[0].firstChild.nodeValue not in tags:
            tags.append(version.getElementsByTagName('empfänger')[0].firstChild.nodeValue[:127])
    except:
        pass
    try:
        if version.getElementsByTagName('produkt')[0].firstChild.nodeValue not in tags:
            tags.append(version.getElementsByTagName('produkt')[0].firstChild.nodeValue[:127])
    except:
        pass
    try:
        if version.getElementsByTagName('sprache')[0].firstChild.nodeValue not in tags:
            tags.append(version.getElementsByTagName('sprache')[0].firstChild.nodeValue[:127])
    except:
        pass
    try:
        if version.getElementsByTagName('kundennummer')[0].firstChild.nodeValue not in tags:
            tags.append(version.getElementsByTagName('kundennummer')[0].firstChild.nodeValue[:127])
    except:
        pass
    try:
        if version.getElementsByTagName('hauptordner')[0].firstChild.nodeValue not in tags:
            tags.append(version.getElementsByTagName('hauptordner')[0].firstChild.nodeValue[:127])
    except:
        pass
    try:
        if version.getElementsByTagName('ordner')[0].firstChild.nodeValue not in tags:
            tags.append(version.getElementsByTagName('ordner')[0].firstChild.nodeValue[:127])
    except:
        pass
    try:
        extkeyvalue = version.getElementsByTagName('ordner-extkey')[0].firstChild.nodeValue
        for key in extkeyvalue.split(","):
            if key.strip() not in tags:
                tags.append(key.strip())
    except:
        pass   
    try:
        letzte_aenderung = version.getElementsByTagName('letzte-änderung')[0].firstChild.nodeValue
    except:
        pass   
    try:
        created = version.getElementsByTagName('datum')[0].firstChild.nodeValue
    except:
        pass   
    try:
        dokumentenart = version.getElementsByTagName('dokumentenart')[0].firstChild.nodeValue
    except:
        pass  
    try:
        ordner = version.getElementsByTagName('ordner')[0].firstChild.nodeValue
    except:
        pass  
    try:
        correspondent = version.getElementsByTagName('firmabehördeverein')[0].firstChild.nodeValue
    except:
        pass 
    try:
        iban = version.getElementsByTagName('iban')[0].firstChild.nodeValue
    except:
        pass 
    try:
        bemerkung = version.getElementsByTagName('bemerkung')[0].firstChild.nodeValue
    except:
        pass 
    try:
        revision = version.getElementsByTagName('revision')[0].firstChild.nodeValue
    except:
        pass 
    try:
        status = version.getElementsByTagName('status')[0].firstChild.nodeValue
    except:
        pass 
    try:
       erhaltenerstellt = version.getElementsByTagName('erhaltenerstellt')[0].firstChild.nodeValue
    except:
        pass 
    try:
       bezahlt_am = version.getElementsByTagName('bezahlt-am')[0].firstChild.nodeValue
    except:
        pass 
    try:
       empfänger = version.getElementsByTagName('empfänger')[0].firstChild.nodeValue
    except:
        pass 
    try:
       bestellnummer = version.getElementsByTagName('bestellnummer')[0].firstChild.nodeValue
    except:
        pass 
    try:
       kundennummer = version.getElementsByTagName('kundennummer')[0].firstChild.nodeValue
    except:
        pass 
    try:
       betragsumme = version.getElementsByTagName('betragsumme')[0].firstChild.nodeValue
    except:
        pass 
    try:
       rechnungsnummer = version.getElementsByTagName('rechnungsnummer')[0].firstChild.nodeValue
    except:
        pass 
    try:
       auftragsnummer = version.getElementsByTagName('auftragsnummer')[0].firstChild.nodeValue
    except:
        pass 
    try:
       bestellung_vom = version.getElementsByTagName('bestellung-vom')[0].firstChild.nodeValue
    except:
        pass 
    try:
       unterzeichnet_von = version.getElementsByTagName('unterzeichnet-von')[0].firstChild.nodeValue
    except:
        pass 
    try:
       unterzeichnet_am = version.getElementsByTagName('unterzeichnet-am')[0].firstChild.nodeValue
    except:
        pass 
    try:
       produkt = version.getElementsByTagName('produkt')[0].firstChild.nodeValue
    except:
        pass 
    try:
       sprache = version.getElementsByTagName('sprache')[0].firstChild.nodeValue
    except:
        pass 

    #null is the value for folder or extkey if nothing is filled in
    if 'null' in tags:
        tags.remove('null')

    if correspondent == '---':
        correspondent == ""

    if bemerkung == '---':
        bemerkung == ""

    metadata = {
        'tags' : tags,
        'correspondent' : correspondent[:127],
        'created' : created,
        'revision' : revision,
        'bemerkung' : bemerkung[:127],
        'ordner' : ordner[:127],
        'hauptordner' : hauptordner[:127],
        'letzte_änderung' : letzte_aenderung,
        'status' : status[:127],
        'erhaltenerstellt' : erhaltenerstellt,
        'bezahlt_am' : bezahlt_am,
        'empfänger' : empfänger[:127],
        'bestellnummer' : bestellnummer[:127],
        'kundennummer' : kundennummer[:127],
        'betragsumme' : betragsumme[:127],
        'iban' : iban[:127],
        'rechungsnummer' : rechnungsnummer[:127],
        'auftragsnummer' : auftragsnummer[:127],
        'bestellung_vom' : bestellung_vom,
        'unterzeichnet_von' : unterzeichnet_von[:127],
        'unterzeichnet_am' : unterzeichnet_am,
        'produkt' : produkt[:127],
        'sprache' : sprache[:127],
        'document_type': dokumentenart
    }
    return metadata
    
def getFileInformation(document):
    files = document.getElementsByTagName('files')
    filename = archiveFolder + files[0].attributes['filePath'].value
    origFilename = files[0].attributes['origname'].value
    id = files[0].attributes['id'].value
    fileOwner = None
    # Now we set the backup file information. Let's see if there are better suitable versions
    fileVersion = files[0].getElementsByTagName('fileVersion')
    if len(fileVersion) > 0:
        maxVersionId = 0
        maxVersion = 0
        # extract username
        user_elements = fileVersion[0].getElementsByTagName("user")
        if len(user_elements) > 0 and user_elements[0].firstChild:
            fileOwner = user_elements[0].firstChild.nodeValue
        for fV in fileVersion:
            if int(fV.attributes['version'].value) > maxVersionId:
                maxVersion = fV
                maxVersionId = int(fV.attributes['version'].value)
        if maxVersionId > 0:
            if pathlib.Path(fV.attributes['origname'].value).suffix.lower() in supportedFiletyped:
                origFilename = fV.attributes['origname'].value
                filename = archiveFolder + fV.attributes['filePath'].value
            # else:
                # try:
                #     origFilename = fV.getElementsByTagName('pdfFile')[0].attributes['origName'].value
                #     filename = archiveFolder + fV.getElementsByTagName('pdfFile')[0].attributes['filePath'].value
                # except:
                #     pass

    mime_type = mimetypes.guess_type(filename)

    fileInformation = {
        'id': id,
        'filename' : filename,
        'origFilename' : origFilename,
        'fileOwner' : fileOwner,
        'RAW_XML' : document.toxml(),
        'MIME_TYPE' : mime_type,
    }
    return fileInformation

def createAndEnsureTags(importData, token_header):
    #Get all known tags
    print(headers_token)
    r = requests.get(
        paperlessurl + "/api/tags/",
        verify=paperlesscert,
        headers=token_header
    )
    results = r.json()["results"]
    while r.json()["next"] != None:
        r = requests.get(
            r.json()["next"],
            verify=paperlesscert,
            headers=token_header,
        )
        results = results + r.json()["results"]

    pltags = {}
    for t in results:
        pltags[t["name"]] = t["id"]

    for doc in importData:
        newtags = []
        for tag in importData[doc]["tags"]:
            if tag in pltags:
                newtags.append(str(pltags[tag]))
            else:
                r = requests.post(
                    paperlessurl + "/api/tags/",
                    verify=paperlesscert,
                    headers=token_header,
                    data={
                        "name": tag
                    }
                )
                if r.status_code == 400:
                    print(f"Tag {tag} was not created successfully")
                    print(r.content)
                newtags.append(str(r.json()["id"])) 
                pltags[tag] = str(r.json()["id"])
        importData[doc]["tags"] = newtags

def createAndEnsureCorrespondents(importData, token_header):
    #Get all known correspondents
    r = requests.get(
        paperlessurl + "/api/correspondents/",
        verify=paperlesscert,
        headers=token_header,
    )
    results = r.json()["results"]
    while r.json()["next"] != None:
        r = requests.get(
            r.json()["next"],
            verify=paperlesscert,
            headers=token_header,
        )
        results = results + r.json()["results"]
    
    plcorrespondents = {}
    for c in results:
        plcorrespondents[c["name"]] = c["id"]

    for doc in importData:
        if importData[doc]["correspondent"] == "":
            continue
        if importData[doc]["correspondent"] in plcorrespondents:
            importData[doc]["correspondent"] = str(plcorrespondents[importData[doc]["correspondent"]])
        else:
            r = requests.post(
                paperlessurl + "/api/correspondents/",
                verify=paperlesscert,
                headers=token_header,
                data={
                    "name": importData[doc]["correspondent"]
                }
            )
            if r.status_code == 400:
                print(f"Correspondent {importData[doc]['correspondent']} was not created successfully")
                print(r.text)
            plcorrespondents[importData[doc]["correspondent"]] = paperlessurl + "/api/correspodents/" + str(r.json()["id"])
            importData[doc]["correspondent"] = paperlessurl + "/api/correspodents/" + str(r.json()["id"])   

def createAndEnsureDocumentTypes(importData, token_header):
    #Get all known correspondents
    r = requests.get(
        paperlessurl + "/api/document_types/",
        verify=paperlesscert,
        headers=token_header,
    )
    results = r.json()["results"]
    while r.json()["next"] != None:
        r = requests.get(
            r.json()["next"],
            verify=paperlesscert,
            headers=token_header,
        )
        results = results + r.json()["results"]
    
    pldoctypes = {}
    for c in results:
        pldoctypes[c["name"]] = c["id"]

    for doc in importData:
        print(importData[doc])
        if importData[doc]["document_type"] == "":
            continue
        if importData[doc]["document_type"] in pldoctypes:
            print(f'Set {pldoctypes[importData[doc]["document_type"]]} for {importData[doc]["document_type"]}')
            importData[doc]["document_type"] = str(pldoctypes[importData[doc]["document_type"]])
        else:
            r = requests.post(
                paperlessurl + "/api/document_types/",
                verify=paperlesscert,
                headers=token_header,
                data={
                    "name": importData[doc]["document_type"]
                }
            )
            if r.status_code == 400:
                print(f"Document type {importData[doc]['document_type']} was not created successfully")
                print(r.text)
            pldoctypes[importData[doc]["document_type"]] = str(r.json()["id"])
            importData[doc]["document_type"] = str(r.json()["id"])      

def get_user_id(username, token_header):
    response = requests.get(f"{paperlessurl}/api/users/", headers=token_header)
    response.raise_for_status()
    print(f"Response: {response.status_code}, Details: {response.text}")

    if response.status_code == 200:
        users_data = response.json()
        users = users_data.get("results", [])

        for user in users:
            if user["username"] == username:
                return user["id"]
            
    else:
        return -1

def set_document_owner(document_id, user_id, token_header):
    try:
        data = {"owner": user_id}
        response = requests.patch(f"{paperlessurl}/api/documents/{document_id}/", headers=token_header, json=data)
        response.raise_for_status()
        print(f"Response: {response.status_code}, Details: {response.text}")
        return response.status_code
    except:
        return 400

def postPaperless(doc, token_header):
    # First: check if doc is blacklisted:
    if doc['id'] in blacklisted_ids:
        print("Skipping document, it is blacklisted...")
        return

    posturl = f"{paperlessurl}/api/documents/post_document/"
    multipartFields = {}

    if doc['bemerkung'] != "" and doc['bemerkung'] != "null":
        multipartFields["title"] = doc['bemerkung']
    if doc['correspondent'] != "" and doc['correspondent'] != "null":
        multipartFields["correspondent"] = doc['correspondent']
    multipartFields["tags"] = doc["tags"]
    if doc['document_type'] != "" and doc['document_type'] != "null":
        multipartFields["document_type"] = doc['document_type']
    if doc['created'] != "" and doc['created'] != "null":
        multipartFields["created"] = doc['created']

    # Prepare custom fields
    custom_fields = {
        27: doc['MIME_TYPE'],
        26: "PAPERLESS_ID",
        24: doc['id'],
        25: doc['revision'],
        16: doc['status'],
        18: doc['ordner'],
        20: doc['hauptordner'],
        17: doc['letzte_änderung'],
        15: doc['erhaltenerstellt'],
        13: doc['bezahlt_am'],
        12: doc['empfänger'],
        11: doc['bestellnummer'],
        10: doc['kundennummer'],
        23: doc['betragsumme'],
        8: doc['iban'],
        7: doc['rechungsnummer'],
        6: doc['auftragsnummer'],
        5: doc['bestellung_vom'],
        4: doc['unterzeichnet_von'],
        3: doc['unterzeichnet_am'],
        2: doc['produkt'],
        1: doc['sprache'],
    }

    # if field is an option-field, get ID and set ID to value:
    status_value_to_id_mapping = {
        "Erledigt": "u0GPKkqaC1kp8MhK",
        "Wiedervorlage": "HjypLQb94UwbkalJ",
        "Zu bearbeiten": "TolUzzhXLj0TkfIV",
    }
    sprache_value_to_id_mapping = {
        "DE": "S5852bpYBL2sQFMp",
        "EN": "tae6wMgm831c5Evi",
        "IT": "KRKHg3xurZeIoUHJ",
    }

    #convert special datetime strings to date if set
    if doc['letzte_änderung'] != "" and doc['letzte_änderung'] != "null":
        custom_fields[17] = datetime.strptime(doc['letzte_änderung'], '%Y-%m-%d %H:%M:%S.%f').strftime('%Y-%m-%d')

    custom_fields[16] = status_value_to_id_mapping.get(doc['status'])
    custom_fields[1] = sprache_value_to_id_mapping.get(doc['sprache'])

    custom_fields = {k: v for k, v in custom_fields.items() if v is not None}
    custom_fields = {k: v for k, v in custom_fields.items() if v is not ''}
    custom_fields_only_ids = custom_fields.keys()
    multipartFields["custom_fields"] = custom_fields_only_ids

    print(multipartFields)
    print(custom_fields)

    # POSTing document
    r = requests.post(
        posturl,
        verify = paperlesscert,
        headers=token_header,
        data=multipartFields, 
        files={'document': (doc['origFilename'], open(doc['filename'], 'rb')) }
    )
    print(r.text)

    if r.status_code == 200:
        # Get task ID
        task_id = r.json()  
        print(f"Task-ID: {task_id}")
        task_url = f"{paperlessurl}/api/tasks/?task_id={task_id}"
        status = None
        while True:
            try:
                response = requests.get(task_url, verify = paperlesscert, headers=token_header)
                task_list = response.json()
                if task_list and len(task_list) > 0:
                    task_data = task_list[0]
                    status = task_data.get("status")
                    print(f"GET: {status}, waiting for SUCCESS or FAILURE")
                    if status == "SUCCESS":
                        break
                    if status == "FAILURE":
                        break
                else:
                    print("Error: No valid task found.")
                    print(f"Response: {response.status_code}, Details: {response.text}")
                    break
            except socket_error as serr:
                if retry_task_api:
                    print("Error: Connection refused, retry after sleep...")
                    time.sleep(task_api_polling_refused_sleep) # Wait to prevent for rate limiting
                    pass
                else:
                    return
            time.sleep(task_api_polling_interval) # Wait for success...

        document_id = -1

        # Check, if document was an duplicate (already imported)
        override_duplicate = bool(False)
        if alter_duplicate_documents:
            try:
                if task_data.get("status") != "SUCCESS":
                    document_id = task_data.get("related_document")
                    if document_id:
                        if document_id != "" or document_id != "null" or document_id != None:
                            override_duplicate = bool(True)
                            print("Document already imported, setting document ID to document ID in paperless.")
                        else:
                            document_id = -1
                            print("Error message not recognized, can not extract duplicate document ID from paperless!")
            except:
                print("Other error occured, see details above.")
                pass

        if (task_list and len(task_list) > 0) or override_duplicate:
            result = task_data.get("status")
            if (result == "SUCCESS") or override_duplicate:
                print(f"GET: {task_data}")
                if not override_duplicate:
                    # Only get document ID from result, if no duplicate, otherwise is already set.
                    document_id = task_data.get("related_document")
                print(f"Document-ID: {document_id}")

                # Now adding RAW XML as note to document
                if add_note_xml:
                    update_note_url = f"{paperlessurl}/api/documents/{document_id}/notes/"
                    update_note_json = {"note": doc['RAW_XML']}
                    update_note_response = requests.post(update_note_url, verify = paperlesscert, headers=token_header, json=update_note_json)
                    print(f"Response: {update_note_response.status_code}, Details: {update_note_response.text}")
                    if update_note_response.status_code == 200:
                        print("Note sucessfully added to document.")
                    else:
                        print("Error, see details above.")

                # Set the custom fields to values
                if add_custom_fields:
                    update_url = f"{paperlessurl}/api/documents/bulk_edit/"

                    # Set ID-Field from POST response
                    custom_fields[26] = document_id

                    for field_id, field_value in custom_fields.items():
                        payload = {
                            "documents": [int(document_id)],
                            "method": "modify_custom_fields",
                            "parameters": {
                                "add_custom_fields": {field_id: field_value},  # Set onyl on field at time
                                "remove_custom_fields": []  # Empty array
                            }
                        }
                        print(f"POST: {payload}")
                        bulk_response = requests.post(update_url, verify=paperlesscert, headers=token_header, json=payload)
                        print(f"Response: {bulk_response.status_code}, Details: {bulk_response.text}")
                        if bulk_response.status_code == 200:
                            print("Bulk edit successful.")
                        else:
                            print("Bulk update failed, see details above.")
                            if not skip_bulk_errors:
                                return
            else:
                print(f"Task failed: {task_data}")
                print("Task exited, but no doc ID returned, see details above.")

                if not skip_documents:
                    return
        else:
            print("Error: No valid result.")
            if not skip_documents:
                return

        if alter_document_owner:
            # Set user permissions (owner) if document ID and owner is valid
            if document_id != -1:
                if doc['fileOwner'] != "" or doc['fileOwner'] != "null" or doc['fileOwner'] != None:
                    user_id = get_user_id(doc['fileOwner'], token_header)
                    if not user_id == -1:
                        if set_document_owner(document_id, user_id, token_header) == 200:
                            print("Document owner changed successful.")
                        else:
                            print("Error changing Document owner!")
                            if not skip_owner_errors:
                                return
                    else:
                        print("Error setting owner: No valid user mapping found!")
                        if not skip_owner_errors:
                            return
        
    if r.status_code == 400:
        print(f"Doc {doc} was not created successfully. multipartFields: {multipartFields}")
        print(r.text)
        if not skip_documents:
            return

def main():
    # Set arguments if set by user via cmd:
    parser = argparse.ArgumentParser(description='Start index and end index')
    parser.add_argument('--start', type=int, default=0, help='Start-Index (Default: 0)')
    parser.add_argument('--end', type=int, default=-1, help='End-Index (Default: -1 for interate to end)')

    args = parser.parse_args()
    start_index = args.start
    end_index = args.end

    # Token handling (if no token is provided, use basic auth, to get token)
    if paperlesstoken == "":
        # No token provided, try to get token via API and basic auth
        login_url = f"{paperlessurl}/api/token/"
        payload = {
            "username": {paperlessuser},
            "password": {paperlesspassword}
        }
        tokenresponse = requests.post(login_url, data=payload)

        if tokenresponse.status_code == 200:
            token = tokenresponse.json().get("token")
            print("Token extracted:", token)
            headers_token = {"Authorization": f"Token {token}"}
        else:
            print("Login failed:", tokenresponse.status_code, tokenresponse.text)
            exit
    else:
        # Token already provided, set auth header
        headers_token = {"Authorization": f"Token {paperlesstoken}"}
        print("Using token with headers:", headers_token)

    importData = {}
    print("Reading XML-File...")
    with minidom.parse(exportXMLFile) as xml:
        documents = xml.getElementsByTagName('document')

        if end_index == -1 or end_index > len(documents):
            end_index = len(documents)

        for i in range(start_index, end_index):
            d = documents[i]
            # Find newest version and use this to extract information
            # 
            fileInformation = getFileInformation(d)
            versions = d.getElementsByTagName('Version')
            newestVersion = versions[0]
            for v in versions:
                if float(v.getElementsByTagName('revision')[0].firstChild.nodeValue) > float(newestVersion.getElementsByTagName('revision')[0].firstChild.nodeValue):
                    newestVersion = v
            metaInformation = getVersionMetadata(newestVersion)
            importData[fileInformation['id']] = fileInformation | metaInformation

    createAndEnsureTags(importData, headers_token)
    createAndEnsureCorrespondents(importData, headers_token)
    createAndEnsureDocumentTypes(importData, headers_token)

    for id in importData:
        print(f"Post data of {id}")
        postPaperless(importData[id], headers_token)
            

if __name__ == "__main__":
    main()
