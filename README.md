This script reads an ecodms-export and imports the documents to paperless-ngx.

This script is customized for my ecoDMS installation. 
The original script is from https://github.com/eingemaischt/ecodmstopaperlessngx-.

To use this script, create an export in ecodms (version 24.02 in my case) with a search string
like "docid >= 0". This will export all of your documents in a zip file with an xml-file "export.xml"

Please be aware that importing self defined metadata requires customization.
Feel free to alter this code to include Metadata in the title - in my case I use my field "bemerkung" as title.

Please configure your environment (place of the ecodms export and paperless instance) in the first lines of the script.
You can use basic auth or token auth.

Please take this script as inspiration - it was build exactly for my use case and it does not include 
any sanity checks or precautions. Please make a backup of your paperless instance....
