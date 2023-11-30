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
rxcui_api_url = 'https://rxnav.nlm.nih.gov/REST/rxcui.json?'
interaction_api_url = 'https://rxnav.nlm.nih.gov/REST/interaction/list.json'
filepath = './patient_data.csv'

# Database Queries
##################
def existsPatientInCsv(filepath, patient_name):    
    with open(filepath, mode='r', newline='') as file:
        csv_reader = csv.DictReader(file)
        for row in csv_reader:
            if row['patient_name'] == patient_name:
                return True
    return False

def getPatientEntityFromCsv(filepath, patient_name_to_check):    
    with open(filepath, mode='r', newline='') as file:
        csv_reader = csv.DictReader(file)
        for row in csv_reader:
            if row['patient_name'] == patient_name_to_check:
                return row
    return None

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

# Helper Methods
################
def extractPatientDetailsFromRequest(request_data):    
    patient_name = request_data['patient_name']
    patient_birthday = request_data['birthday']
    patient_prescription = request_data['prescription']
    process_instance_id = request_data['process_instance_id']
    return patient_name, patient_birthday, patient_prescription, process_instance_id

def extractConfirmationEmailFromRequest(request_data):    
    patient_name = request_data['patient_name']    
    patient_birthday = request_data['birthday']    
    patient_prescription = request_data['prescription']    
    pharmacych = request_data['pharmacych']    
    email_patient = request_data['email_patient']    
    email_doctor = request_data['email_doctor']    
    
    return patient_name, patient_birthday, patient_prescription, email_patient, email_doctor, pharmacych

def generateCheckPatientDataResponse(status, message, patient_name, birthday, prescription):
    value = {
        "status": status,
        "message": message,        
        "patient_name": patient_name,
        "birthday": birthday,
        "prescription": prescription
    }    
    return json.dumps(value)

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

def emailResponseTempalte(method, title, text):
    return "<p>" + method + " " + title + " </p><p>" + text + "</p>"



from tempfile import NamedTemporaryFile
import shutil

# API Routing
#############
@app.route("/")
def ehr_app():
    return "This is an Electronic Health Record service."

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

# @Bojana
# 1. Fetch the patient_id, patient_name, birthday, perscription from request
# 2. check if database contains patient_name    
# 3. return whether patient exists or not
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
            email_content = emailResponseTempalte("NOT EXISTENT", " - Perscription Canceled", "You are not registered to the EHR System and thus not allowed to use it.")
            response = generateCheckPatientDataResponse("false", email_content, name, birthday, prescription)
            print(response)
            return response, 404
    return {"error": "Request must be JSON"}, 415

# @Gerardo
# 1. Fetch the patient_id, patient_name, perscription from request
# 2. you can take example of checking for duplicates from the following Method 'existsPatientInCsv'...
        # but prevent the early stopping and work with a index counter (like counting how many times patient_name and perscription occur in the DB)
# 3. evaluate the index counter
# if counter > 1 => return true
# if counter < 1 => return false
# if counter == 1 => return true
# 4. return whether you are successfull or not
@app.route('/patient/check/duplicates', methods=['POST'])
def checkForDuplicates():
    if request.is_json:
        print("called /patient/check/duplicates")
        name, birthday, prescription, process_instance_id = extractPatientDetailsFromRequest(request.json)
        has_duplicate = False
        with open(filepath, mode='r', newline='') as file:
            csv_reader = csv.DictReader(file)
            counter = 0
            for row in csv_reader:
                if (row["patient_name"] == name and prescription in row["prescription"]):
                    counter += 1            
            if counter < 1:
                has_duplicate = False
            elif counter == 1:
                has_duplicate = False #True
            else:
                has_duplicate = False #True
        response = generateCheckPatientDataResponse(str(has_duplicate), "duplication", name, birthday, prescription)
        print(response)
        return response, 201    
    return {"error": "Request must be JSON"}, 415
  

# @Sebastian
# 1. Fetch the patient_id, patient_name, birthday, perscription from request
# 2. get list of perscriptions in database for patient_name
# 3. return if drug-interactions (true/false)
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

# @Magdalena
# 1. Fetch the patient_id, patient_name, birthday, perscription from request
# 2. parse the parameters form the request and generate a comman separated string        
# 3. update the perscription with (',') in the csv
# 4. return whether you are successfull or not
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
    