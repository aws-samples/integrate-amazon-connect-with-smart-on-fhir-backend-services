import logging, json, random, string, os, base64, boto3, urllib3
from datetime import datetime, timedelta, timezone
logger = logging.getLogger()
logger.setLevel(logging.INFO)

class FHIRClient:
    """
    A class as connection client to SMART on FHIR backend services. 
    Parameters:
      client_id: can be download from Epic App Orchard
      endpoint_token: URL to retrieve the JWT token
      endpoint_stu3: FHIR RESTful endpoint
      kms_key_id: KMS customer managed key 
    """
    http=urllib3.PoolManager()
    kms_client = boto3.client('kms')

    def __init__(self, client_id, endpoint_token, endpoint_stu3, kms_key_id):
        self.client_id = client_id
        self.endpoint_token = endpoint_token
        self.endpoint_stu3 = endpoint_stu3
        self.kms_key_id = kms_key_id


    def get_access_token(self, clientid, audience, expires_in_minutes=4):
        segments = []

        header_dict = {
          "alg": "RS384",
          "typ": "JWT"
        }
        header = json.dumps(header_dict, separators=(",", ":")).encode("utf-8")
        segments.append( base64.urlsafe_b64encode(header).replace(b"=", b"") )

        tmpexp = datetime.now(timezone.utc) + timedelta(minutes=expires_in_minutes)
        tmpintexp = int((tmpexp - datetime(1970, 1, 1, tzinfo=timezone.utc)).total_seconds())
        payload_dict = {
            'iss': clientid,
            'sub': clientid,
            'aud': audience,
            'jti': ''.join(random.choice(string.ascii_letters) for i in range(150)),
            'exp': tmpintexp
        }
        payload = json.dumps(payload_dict, separators=(",", ":")).encode("utf-8")
        segments.append( base64.urlsafe_b64encode(payload).replace(b"=", b"") )
        signing_input = b".".join(segments)
        logger.debug('signing input: {}'.format(signing_input.decode("utf-8")))

        response = self.kms_client.sign(
            KeyId=self.kms_key_id,
            Message=signing_input,
            MessageType='RAW',
            SigningAlgorithm='RSASSA_PKCS1_V1_5_SHA_384'      ## 'RSASSA_PSS_SHA_384'|'ECDSA_SHA_384'
        )
        signature = base64.urlsafe_b64encode(response['Signature']).replace(b"=", b"")
        logger.debug('signature: {}'.format( signature ))
        segments.append( signature )
        encoded = b".".join(segments)
        logger.debug('encoded: {}'.format(encoded.decode("utf-8")))
        
        postData = {
            'grant_type' : 'client_credentials',
            'client_assertion_type': 'urn:ietf:params:oauth:client-assertion-type:jwt-bearer',
            'client_assertion': encoded
        };
        r = self.http.request('POST', audience, fields=postData)
        logger.debug(json.loads(r.data.decode()))
        
        return {
            'status': r.status,
            'data': json.loads(r.data.decode())
        }
        
    def find_appointments(self, apppointment_date):
        res_token = self.get_access_token(self.client_id, self.endpoint_token)
        
        if res_token['status'] == 200:
            headers = {'Authorization': 'Bearer {}'.format(res_token['data']['access_token']), 'Content-Type': 'application/json'}
            logger.debug(headers)
            
            postData={
                "resourceType": "Parameters",
                "parameter": [
                    {
                        "name": "startTime",
                        "valueDateTime": apppointment_date.strftime("%Y-%m-%dT%H:%M:%SZ") 
                    },
                    {
                        "name": "endTime",
                        "valueDateTime": (apppointment_date + timedelta(days=1)).strftime("%Y-%m-%dT%H:%M:%SZ") 
                    }
                ]
            }
            
            r = self.http.request('POST', self.endpoint_stu3+'Appointment/$find', body=json.dumps(postData), headers=headers)
            if r.status == 200:
                dat = json.loads(r.data.decode())
                appointments = []
                for entry in dat['entry']:
                    appointment = {}
                    appointment['id'] = entry['resource']['id']
                    appointment['status'] = entry['resource']['status']
                    appointment['start'] = entry['resource']['start']
                    appointment['end'] = entry['resource']['end']
                    appointment['minutesDuration'] = entry['resource']['minutesDuration']
                    appointment['serviceType'] = entry['resource']['serviceType'][0]['coding'][0]['display']
                    appointment['slot'] = entry['resource']['slot'][0]['display']
                    appointment['schedule'] = entry['resource']['contained'][0]['schedule']['reference']
                    appointment['participants'] = []
                    participants = entry['resource']['participant']
                    for p in participants:
                        participant = {}
                        participant['reference'] = p['actor']['reference']
                        participant['name'] = p['actor']['display']
                        participant['status'] = p['status']
                        appointment['participants'].append(participant)
                    appointments.append(json.dumps(appointment))
                response = appointments
            else:
                response = dat['issue'][0]
            return {
                'status': r.status,
                'response': appointments
            }
        else: 
            return {
                'status': 400,
                'response': 'JWT token not found'
            }

    def book_appointments(self, patientid, appointmentid, appointmentnote):
        res_token = self.get_access_token(self.client_id, self.endpoint_token)
        
        if res_token['status'] == 200:
            headers = {'Authorization': 'Bearer {}'.format(res_token['data']['access_token']), 'Content-Type': 'application/json'}
            logger.debug(headers)
            
            postData={
                'resourceType': 'Parameters',
                'parameter': [
                    {
                        'name': 'patient',
                        'valueIdentifier': {'value': patientid}
                    },
                    {
                        'name': 'appointment',
                        'valueIdentifier': {'value': appointmentid}
                    },
                    {
                        'name': 'appointmentNote',
                        'valueString': appointmentnote
                    }
                ]
            }
            
            r = self.http.request('POST', self.endpoint_stu3+'Appointment/$book', body=json.dumps(postData), headers=headers)
            dat = json.loads(r.data.decode())
            if r.status == 200:
                entry = dat['entry'][0]
                appointment = {}
                appointment['id'] = entry['resource']['id']
                appointment['status'] = entry['resource']['status']
                appointment['start'] = entry['resource']['start']
                appointment['end'] = entry['resource']['end']
                appointment['minutesDuration'] = entry['resource']['minutesDuration']
                appointment['serviceType'] = entry['resource']['serviceType'][0]['coding'][0]['display']
                appointment['participants'] = []
                participants = entry['resource']['participant']
                for p in participants:
                    participant = {}
                    participant['reference'] = p['actor']['reference']
                    participant['name'] = p['actor']['display']
                    participant['status'] = p['status']
                    appointment['participants'].append(participant)
                response = appointment
            else:
                response = dat['issue'][0]
            return {
                'status': r.status,
                'response': response
            }
        else: 
            return {
                'status': 400,
                'response': 'JWT token not found'
            }

    def get_patient(self, patientinfo):
        res_token = self.get_access_token(self.client_id, self.endpoint_token)
        
        if res_token['status'] == 200:
            headers = {'Authorization': 'Bearer {}'.format(res_token['data']['access_token']), 'Content-Type': 'application/json'}
            logger.debug(headers)

            r = self.http.request('GET', self.endpoint_stu3+'Patient', fields=patientinfo, headers=headers)
            dat = json.loads(r.data.decode())
            if r.status == 200:
                response = dat['entry'][0]['resource']['id']
            else:
                response = dat['issue'][0]
            return {
                'status': r.status,
                'response': response
            }
        else: 
            return {
                'status': 400,
                'response': 'JWT token not found'
            }
        return ''

    def get_meds(self, patient_id):
        res_token = self.get_access_token(self.client_id, self.endpoint_token)
        
        if res_token['status'] == 200:
            headers = {'Authorization': 'Bearer {}'.format(res_token['data']['access_token']), 'Content-Type': 'application/json'}
            logger.debug(headers)
            
            r = self.http.request('GET', self.endpoint_stu3+'MedicationStatement', fields=patient_id, headers=headers)
            if r.status == 200:
                dat = json.loads(r.data.decode())
                logger.info(dat)
                medications = []
                for entry in dat['entry']:
                    ms = entry['resource']['MedicationStatement']
                    medication = {}
                    if ms['dosage']['patientInstruction'] is not None:
                        medication['dosage'] = ms['dosage']['patientInstruction']
                    if ms['medicationReference']['display'] is not None:
                        medication['medicationReference'] = ms['medicationReference']['display']
                    medications.append(json.dumps(medication))
                response = medications
            else:
                response = r.data.decode()
                logger.info(r)
            return {
                'status': r.status,
                'response': response
            }
        else: 
            return {
                'status': 400,
                'response': 'JWT token not found'
            }

