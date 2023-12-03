import requests
import csv
import logging
import json
import pandas as pd
from flask import Flask, jsonify, request
app = Flask(__name__)

# Global vars
#############
log_file_path = './log6.log'
logging.basicConfig(filename=log_file_path, level=logging.DEBUG, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)
camunda_api_url = 'https://digibp.herokuapp.com/engine-rest'

# NLM API to identify drugs by rxNorms 
    # and resolve the error of misspelling or not existing pharmaceutical ingredient
rxcui_api_url = 'https://rxnav.nlm.nih.gov/REST/rxcui.json?'

# NLM API for drug Interaction discovery
    # and checks if interactions with other drugs is performed
interaction_api_url = 'https://rxnav.nlm.nih.gov/REST/interaction/list.json'

# The EHR database consist out of the following column's:
    # patient_id --> as described in the disclaimer in production this ID shall be replaced by AHV-Nr.
    # patient_name
    # birthday
    # gender
    # prescription --> this is a comma separated list of active pharmaceutical ingredients that are already prescribed.
filepath = './patient_data.csv' 
    

# Database Queries
##################
# Check if patient exists in database by `patient_name`
def existsPatientInCsv(filepath, patient_name):    
    with open(filepath, mode='r', newline='') as file:
        csv_reader = csv.DictReader(file)
        for row in csv_reader:
            if row['patient_name'] == patient_name:
                return True
    return False

# Finds patient in database by `patient_name`
def getPatientEntityFromCsv(filepath, patient_name_to_check):    
    with open(filepath, mode='r', newline='') as file:
        csv_reader = csv.DictReader(file)
        for row in csv_reader:
            if row['patient_name'] == patient_name_to_check:
                return row
    return None

# This method is not used, as the disclaimer describes 
# Our project aims to connect to the EHR. Therefore, only registered patients will be able to enjoy full service.
def addPatientToCsv(filepath, filename, patient_rec):
        df_patient = pd.read_csv(filepath)
        patient_rec["patient_id"] = max(df_patient["patient_id"]) + 1
        print(df_patient)
        df_patient_new = df_patient.append(patient_rec, ignore_index=True)
        df_patient_new.to_csv(filename, index=False)

        obj = {
            "patient": patient_rec
        }

        return obj

# Helper Methods for API-Requests
################

# Extract data from a json request (patient_name, birthday, prescription, process_instance_id)
    # The process_instance_id is used to identify the process later on, for key_correlation of camunda's tasks called:
    # MESSAGE_INTERMEDIATE_CATCH_EVENT: pharmacy choosen
def extractPatientDetailsFromRequest(request_data):    
    patient_name = request_data['patient_name']
    patient_birthday = request_data['birthday']
    patient_prescription = request_data['prescription']
    process_instance_id = request_data['process_instance_id']
    return patient_name, patient_birthday, patient_prescription, process_instance_id

# Extract data from a json request, which is used to sent an email
def extractConfirmationEmailFromRequest(request_data):    
    patient_name = request_data['patient_name']    
    patient_birthday = request_data['birthday']    
    patient_prescription = request_data['prescription']        
    pharmacych = request_data['pharmacych']        
    email_patient = request_data['email_patient']        
    email_doctor = request_data['email_doctor']    
    
    return patient_name, patient_birthday, patient_prescription, email_patient, email_doctor, pharmacych

# Generates the json-body as response to be sent to camunda
def generateCheckPatientDataResponse(status, message, patient_name, birthday, prescription):
    value = {
        "status": status,
        "message": message,        
        "patient_name": patient_name,
        "birthday": birthday,
        "prescription": prescription
    }    
    return json.dumps(value)

# Generated the json-body as response by email to be sent to camunda and make
def generateConfirmationEmailResponse(patient_name, birthday, prescription, email_doctor, email_patient, email_pharmacy, email_content):
    value = {
        "patient_name": patient_name,
        "birthday": birthday,
        "prescription": prescription,
        "email_doctor": email_doctor,
        "email_patient": email_patient,
        "email_pharmacy": email_pharmacy,
        "email_content": email_content
    }    
    return json.dumps(value)

# Template for equal email styles.
def emailResponseTempalte(method, title, text):
    return "<p>" + method + " " + title + " </p><p>" + text + "</p>"




from tempfile import NamedTemporaryFile
import shutil

# API Routing
#############
@app.route("/")
def ehr_app():
    return "This is an Automated Electronic Health Record service."

# This endpoint checks if the prescribed medication exists in an official drug registry.
# This is done via the API provided by the National Library of Medicine (supported by National Institute of Health)
# https://rxnav.nlm.nih.gov/REST/rxcui
    # Rules:
        # If there is no match in the drug registry the process aborts with a cancellation message. 
        # If the medication exists in the drug registry the subsequent task will be executed.
@app.route('/prescription/check', methods=['POST'])
def checkPrescriptionExists():
    print("called /prescription/check")       
    if request.is_json:
        name, birthday, prescription, process_instance_id = extractPatientDetailsFromRequest(request.json)
        logger.info(f'Processing task for patient: {name}')
        prescription_exists = findRxNormByDrugName(prescription)
        response = None
        if prescription_exists is None:
            email_content = emailResponseTempalte("NOT EXISTENT", " - Perscription Canceled", "The prescription you entered is not existent. <br /> <p>Prescription: "+prescription+"</p>")
            response = generateCheckPatientDataResponse("false", email_content, name, birthday, prescription)
        else:
            response = generateCheckPatientDataResponse("true", "", name, birthday, prescription)            
            
        print(response)
        return response, 404
    return {"error": "Request must be JSON"}, 415

# This endpoint will check if the provided patient name has been registered in the EHR. 
    # Rules:
        # If the patient name is not known the process will abort with a cancellation message to the practitioner.
        # If the patient is registered in the EHR the subsequent task will be executed.
@app.route('/patient/check', methods=['POST'])
def checkPatientData():
    print("called /patient/check")       
    if request.is_json:
        name, birthday, prescription, process_instance_id = extractPatientDetailsFromRequest(request.json)
        logger.info(f'Processing task for patient: {name}')
        print("Process instance ID:")
        print(process_instance_id)
        is_existing_patient = existsPatientInCsv(filepath, name)
        if is_existing_patient:
            logger.info('Patient found.')
            response = generateCheckPatientDataResponse("true", "Patient found", name, birthday, prescription)
            print(response)
            return response, 200
        else:
            logger.info('Patient not found.')
            email_content = emailResponseTempalte("NOT EXISTENT", " - Perscription Canceled", "Your patient is not registered to the EHR System.")
            response = generateCheckPatientDataResponse("false", email_content, name, birthday, prescription)
            print(response)
            return response, 404
    return {"error": "Request must be JSON"}, 415


# This endpoint compares the newly created prescription with the already existing prescriptions in the EHR.
    # Rules:
        # If there is a duplicate prescription the process aborts with a cancellation message to the practitioner.
        # If there is no duplicate prescription detected the subsequent task will be executed.
@app.route('/patient/check/duplicates', methods=['POST'])
def checkForDuplicates():
    print("called /patient/check/duplicates")
    if request.is_json:
        name, birthday, prescription, process_instance_id = extractPatientDetailsFromRequest(request.json)
        search_duplicate_prescription = prescription
        patient = getPatientEntityFromCsv(filepath, name) # fetch existing prescriptions
        previous_prescription_list = patient['prescription'].split(",")
        if any(word in search_duplicate_prescription for word in previous_prescription_list):
            email_content = emailResponseTempalte("DUPLICATE", " - Prescription Canceled", "Your patient has already a similar prescription in our system. To avoid double medication your prescription has been canceled.")
            response = generateCheckPatientDataResponse("true", email_content, name, birthday, prescription)
            print(response)
            return response, 200
        else:
            response = generateCheckPatientDataResponse("false", "no duplicates", name, birthday, prescription)
            print(response)
            return response, 200    
    return {"error": "Request must be JSON"}, 415

# This endpoint checks the new prescription with the already existing prescriptions for drug interactions. 
# This is done in the API provided by the National Library of Medicine (supported by National Institute of Health)
# https://lhncbc.nlm.nih.gov/RxNav/APIs/InteractionAPIs.html 
    # Rules:
        # If an interaction is found, the process will abort with a cancellation message to the practitioner.
        # If there is no interaction detected the next task will be executed.
@app.route('/patient/check/interactions', methods=['POST'])
def checkForInteraction():
    print("/patient/check/interactions")
    if request.is_json:       
        name, birthday, prescription, process_instance_id = extractPatientDetailsFromRequest(request.json)
        patient = getPatientEntityFromCsv(filepath, name) # fetch existing prescriptions
        previous_prescription_list = patient['prescription'].split(",")
        distinct_prescription_list = list(dict.fromkeys(previous_prescription_list)) # distinct prescriptions
        distinct_prescription_list.append(prescription) # add prescription to be issued
        drug_rxNorm_list = []
        for x in distinct_prescription_list:
            drug_rxNorm_list.append(findRxNormByDrugName(x)) # Fetch RxNormID
        drug_rxNorm_list = [i for i in drug_rxNorm_list if i is not None] # filter None's
        interaction_list_tripple = findDrugInteractionsFromList(drug_rxNorm_list) # Fetch drug interactions
        if interaction_list_tripple is None or len(interaction_list_tripple) == 0:
            response = generateCheckPatientDataResponse("false", "no interactions", name, birthday, prescription)
            return response, 200
        # Using a for loop to iterate over each tripple in the list
        for my_tripple in interaction_list_tripple:                        
            print(my_tripple)
            print("!!!WARNING!!! => interaction found")
        email_content = emailResponseTempalte("INTERACTION", "FOUND - Prescription Canceled", str(my_tripple)) 
        response = generateCheckPatientDataResponse("true", email_content, name, birthday, prescription)        
        print(response)
        return response, 200
    return {"error": "Request must be JSON"}, 415


# This endpoint updates the EHR with the new prescription.
@app.route('/patient/updateHealthInformation', methods=['POST'])
def updateHealthInformation():
    if request.is_json:
        print("/patient/updateHealthInformation")
        name, birthday, prescription, process_instance_id = extractPatientDetailsFromRequest(request.json)               
        fields = ['patient_id', 'patient_name', 'birthday', 'gender', 'prescription']
        tempfile = NamedTemporaryFile(mode='w', delete=False)
        with open(filepath, 'r') as csvfile, tempfile:
            reader = csv.DictReader(csvfile, fieldnames=fields)
            writer = csv.DictWriter(tempfile, fieldnames=fields)
            for row in reader:
                if row['patient_name'] == str(name):                
                    old_perscription = row['prescription']                    
                    row['prescription'] = prescription + "," + old_perscription
                row = {'patient_id': row['patient_id'], 'patient_name': row['patient_name'], 'birthday': row['birthday'], 'gender': row['gender'], 'prescription': row['prescription']}
                writer.writerow(row)    
        shutil.move(tempfile.name, filepath)
        header = '<strong>SUCCESS'
        title = '- Prescription accepted!</strong>'
        content = """We would like to inform you that the validation process for the submitted prescription was meticulously executed.<br />
        The system seamlessly interacted with our database, performing essential checks to ensure the integrity and safety of the prescription.<br /><br />
        <strong>The following validations were conducted:</strong><br />
        <strong>  - Patient Existence Check:</strong> The system verified the existence of the patient in our records, confirming the accuracy of the provided patient information.<br />
        <strong>  - Patient Prescription Duplicate Check:</strong> A comprehensive examination was conducted to identify any duplicate prescriptions associated with the patient, ensuring the prevention of redundant or conflicting medication instructions.<br />
        <strong>  - Drug Existence Check:</strong> The system confirmed the presence of the prescribed drugs within our database, validating the availability of the specified medications for dispensation.<br />
        <strong>  - Drug Interactions Check:</strong> In an effort to prioritize patient safety, the system assessed potential interactions between the prescribed drugs, thereby mitigating the risk of adverse effects.<br />
        <br /><br />
        Your commitment to adhering to best practices in prescription submission significantly contributes to the overall efficiency and reliability of our healthcare processes.<br /><br />
        """
        email_content = emailResponseTempalte(header, title, content) 
        response = generateCheckPatientDataResponse("true", email_content, name, birthday, prescription)
        print(response)
        return response, 200
    return {"error": "Request must be JSON"}, 415


# This endpoint creates the response for camunda to collect all neccessary e-mail addresses. 
# Disclaimer: Our project aims to send emails to choosen pharmacies by patient. 
    # However, the pharmacy e-mail addresses are fictional and are changed by real e-mail address upon production
@app.route('/confirmation/email', methods=['POST'])
def confirmEmail():
    if request.is_json:
        print("/confirmation/email")        
        print(request.json)
        name, birthday, prescription, email_patient, email_doctor, pharmacych = extractConfirmationEmailFromRequest(request.json)         
        if pharmacych == "Pharmacy 1, Zurich":
            pharmacy_email = "sebastian@fernandeznet.ch"
        elif pharmacych == "Pharmacy 2, Basel":
            pharmacy_email = "magdalena.hardegger@students.fhnw.ch"
        elif pharmacych == "Pharmacy 3, Bern":
            pharmacy_email = "info@pharmacy3.ch"
        elif pharmacych == "Pharmacy 4, Geneva":
            pharmacy_email = "info@pharmacy4.ch"
        elif pharmacych == "Pharmacy 5, Luzern":
            pharmacy_email = "info@pharmacy5.ch"
        elif pharmacych == "Pharmacy 6, Lugano":
            pharmacy_email = "info@pharmacy6.ch"        
        
        response = generateConfirmationEmailResponse(name, birthday, prescription, email_doctor, email_patient, pharmacy_email, "Test")        
        print(response)
        return response, 200        
    return {"error": "Request must be JSON"}, 415

# This endpoint creates the response for camunda in case the patient did not respond nor collected his prescription
@app.route('/notcollected/email', methods=['POST'])
def notcollectedEmail():
    if request.is_json:
        print("/notcollected/email")                
        name, birthday, prescription, email_patient, email_doctor, pharmacych = extractConfirmationEmailFromRequest(request.json)               
        email_content = emailResponseTempalte("NOT COLLECTED WITHIN 4 WEEKS", " - Perscription Canceled", "Your patient did not collect prescription within 4 weeks.")
        response = generateCheckPatientDataResponse(True, email_content, name, birthday, prescription)
        print(response)
        return response, 200        
    return {"error": "Request must be JSON"}, 415


# Drug Interaction API
######################

def findRxNormByDrugName(drug_name):
# GET https://rxnav.nlm.nih.gov/REST/rxcui.json?name=Amlodipine&allsrc=1
    findRxNormByStringURL = rxcui_api_url + 'name='+drug_name+'&allsrc=1'
    response = requests.get(findRxNormByStringURL)
    if response.status_code == 200:        
        if len(response.json()['idGroup']) == 0:
            return None
        return response.json()['idGroup']['rxnormId']   
    else:
        return None

def findDrugInteractionsFromList(drug_list):
# GET https://rxnav.nlm.nih.gov/REST/interaction/list.json?rxcuis=207106+152923+656659    
    delimiter = '+'        
    delemiter_separated_drug_list = '?rxcuis=' + '+'.join([item for sublist in drug_list for item in sublist]) # [['6809'], ['35636']]    
    findDrugInteractionURL = interaction_api_url + delemiter_separated_drug_list
    response = requests.get(findDrugInteractionURL)
    if response.status_code == 200:
        interaction_tripple = []
        if 'fullInteractionTypeGroup' not in response.json():
            return None        
        interation_group = response.json()['fullInteractionTypeGroup']        
        for group in interation_group:            
            source_name = group['sourceName']
            interaction_type_group = group['fullInteractionType']
            for interactionType in interaction_type_group:
                interactionPair = interactionType['interactionPair']
                for pair in interactionPair:                                             
                    new_tripple = (source_name, pair['severity'], pair['description'])                    
                    interaction_tripple.append(new_tripple)
        return interaction_tripple
    else:
        return None
    