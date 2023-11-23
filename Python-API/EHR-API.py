# hidden (no-copy-paste area)

import requests
import csv
import logging
import json
import pandas as pd
from flask import Flask, jsonify, request
app = Flask(__name__)

# Global vars
#############
log_file_path = './log5.log'
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
    return patient_name, patient_birthday, patient_prescription

def generateCheckPatientDataResponse(status, message, patient_name, birthday, prescription):
    value = {
        "status": status,
        "message": message,        
        "patient_name": patient_name,
        "birthday": birthday,
        "prescription": prescription
    }    
    return json.dumps(value)

def generateCheckDuplicateDataResponse(status, has_duplicate, patient_name, birthday, prescription):
    value = {
        "status": status,        
        "hasDuplicate": has_duplicate,        
        "patient_name": patient_name,
        "birthday": birthday,
        "prescription": prescription     
    }
    return json.dumps(value)

def generateCheckForInteractionResponse(status, has_interaction, patient_name, birthday, prescription):
    value = {
        "status": status,        
        "hasInteraction": has_interaction,        
        "patient_name": patient_name,
        "birthday": birthday,
        "prescription": prescription   
    }
    return json.dumps(value)

from tempfile import NamedTemporaryFile
import shutil

# API Routing
#############
@app.route("/")
def ehr_app():
    return "This is an Electronic Health Record service."

# @Bojana
# 1. Fetch the patient_id, patient_name, birthday, perscription from request
# 2. check if database contains patient_name    
# 3. return whether patient exists or not
@app.route('/patient/check', methods=['POST'])
def checkPatientData():
    print("called /patient/check")       
    if request.is_json:
        name, birthday, prescription = extractPatientDetailsFromRequest(request.json)
        logger.info(f'Processing task for patient: {name}')
        is_existing_patient = existsPatientInCsv(filepath, name)
        if is_existing_patient:
            logger.info('Patient found.')
            response = generateCheckPatientDataResponse("ok", "true", name, birthday, prescription)
            print(response)
            return response, 200
        else:
            logger.info('Patient not found.')
            response = generateCheckPatientDataResponse("fail", "false", name, birthday, prescription)
            print(response)
            return response, 404
    return {"error": "Request must be JSON"}, 415

# @Gerardo
# 1. Fetch the patient_id, patient_name, perscription from request
# 2. you can take example of checking for duplicates from the following Method 'existsPatientInCsv'...
        # but prevent the early stopping and work with a index counter (like counting how many times patient_name and perscription occur in the DB)
# 3. evaluate the index counter
# if counter > 1 => return true
# if counter < 1 => return true
# if counter == 1 => return false
# 4. return whether you are successfull or not
@app.route('/patient/check/duplicates', methods=['POST'])
def checkForDuplicates():
    if request.is_json:
        print("called /patient/check/duplicates")
        name, birthday, prescription = extractPatientDetailsFromRequest(request.json)
        response = generateCheckDuplicateDataResponse("ok", "false", name, birthday, prescription)
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
        name, birthday, prescription = extractPatientDetailsFromRequest(request.json)
        patient = getPatientEntityFromCsv(filepath, name)
        prescription_list = patient['prescription'].split(",")
        distinct_prescription_list = list(dict.fromkeys(prescription_list))
        drug_rxNorm_list = []
        for x in distinct_prescription_list:
            drug_rxNorm_list.append(findRxNormByDrugName(x))
        drug_rxNorm_list = [i for i in drug_rxNorm_list if i is not None]
        interaction_list_tripple = findDrugInteractionsFromList(drug_rxNorm_list)
        if len(interaction_list_tripple) == 0:
            response = generateCheckForInteractionResponse("ok", "false", name, birthday, prescription)
        # Using a for loop to iterate over each tripple in the list
        for my_tripple in interaction_list_tripple:                        
            print(my_tripple)
            #for item in my_tripple:                
            #    print(item)
            print("!!!WARNING!!! => interaction found")
        response = generateCheckForInteractionResponse("ok", "true", name, birthday, prescription)        
        print(response)
        return response, 201
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
        name, birthday, prescription = extractPatientDetailsFromRequest(request.json)               
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
        response = generateCheckPatientDataResponse("ok", "EHR-System updated successfully", name, birthday, prescription)
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
    

# the following line of code will make this notebook act like a server
app.run(host='0.0.0.0', port=8080)