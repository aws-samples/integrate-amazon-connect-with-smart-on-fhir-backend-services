import os
from FHIRClient import FHIRClient
from datetime import datetime, timedelta, timezone
import logging
logger = logging.getLogger()
logger.setLevel(logging.INFO)


def lambda_handler(event, context):
    fhirclient = FHIRClient(
        os.environ['client_id'],
        os.environ['endpoint_token'],
        os.environ['endpoint_stu3'],
        os.environ['kms_key_id']
    )

    patientinfo = {
        'family': 'Mychart', 
        'given': 'Allison',
        'gender': 'Female',
        'telecom': '608-123-4567'
    }
    r = fhirclient.get_patient(patientinfo)
    return {
        'status': r['status'],
        'patientid': r['response']
    }
    
    # patient_id = {
    #     'patient': 'enh2Q1c0oNRtWzXArnG4tKw3'
    # }
    # r = get_meds(patient_id)
    # return {
    #     'status': r['status'],
    #     'medications': r['response']
    # }

    # apppointment_date = datetime(2020, 12, 13)
    # logger.info(apppointment_date)
    # r = fhirclient.find_appointments(apppointment_date)
    # return {
    #     'status': r['status'],
    #     'appointments': r['response']
    # }
  
    # r = fhirclient.book_appointments('eJzlzKe3KPzAV5TtkxmNivQ3', 'ewEuYQHgm49dEDl-ZLGWERy.bykrQlaB8iIv94vR9f.3nsWu0PXEZ-XI-9lZK04PI3', 'MYCHART VIDEO VISIT')
    # return {
    #     'status': r['status'],
    #     'response': r['response']
    # }
