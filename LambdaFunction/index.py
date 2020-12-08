import json, random, string, os, math, time, datetime, dateutil.parser
import boto3
from datetime import datetime, timedelta, timezone
import logging
from FHIRClient import FHIRClient

logger = logging.getLogger()
logger.setLevel(logging.INFO)

## Establish the connection to SMART on FHIR backend services
fhirclient = FHIRClient(
    os.environ['client_id'],
    os.environ['endpoint_token'],
    os.environ['endpoint_stu3'],
    os.environ['endpoint_epic'],
    os.environ['kms_key_id']
)



""" --- Helpers to build responses which match the structure of the necessary dialog actions --- """
def elicit_slot(session_attributes, intent_name, slots, slot_to_elicit, message, response_card):
    return {
        'sessionAttributes': session_attributes,
        'dialogAction': {
            'type': 'ElicitSlot',
            'intentName': intent_name,
            'slots': slots,
            'slotToElicit': slot_to_elicit,
            'message': message,
            'responseCard': response_card
        }
    }


def confirm_intent(session_attributes, intent_name, slots, message, response_card):
    return {
        'sessionAttributes': session_attributes,
        'dialogAction': {
            'type': 'ConfirmIntent',
            'intentName': intent_name,
            'slots': slots,
            'message': message,
            'responseCard': response_card
        }
    }


def close(session_attributes, fulfillment_state, message):
    response = {
        'sessionAttributes': session_attributes,
        'dialogAction': {
            'type': 'Close',
            'fulfillmentState': fulfillment_state,
            'message': message
        }
    }

    return response
  
    
def delegate(session_attributes, slots):
    return {
        'sessionAttributes': session_attributes,
        'dialogAction': {
            'type': 'Delegate',
            'slots': slots
        }
    }


def build_response_card(title, subtitle, options):
    """
    Build a responseCard with a title, subtitle, and an optional set of options which should be displayed as buttons.
    """
    buttons = None
    if len(options) > 1:
        buttons = []
        for i in range(min(5, len(options))):
            buttons.append(options[i])

        return {
            'contentType': 'application/vnd.amazonaws.card.generic',
            'version': 1,
            'genericAttachments': [{
                'title': title,
                'subTitle': subtitle,
                'buttons': buttons
            }]
        }
    else:
        return {
        'contentType': 'application/vnd.amazonaws.card.generic',
        'version': 1,
        'genericAttachments': [{
            'title': title,
            'subTitle': subtitle
        }]
    }


""" --- Helper Functions --- """


def parse_int(n):
    try:
        return int(n)
    except ValueError:
        return float('nan')


def try_ex(func):
    """
    Call passed in function in try block. If KeyError is encountered return None.
    This function is intended to be used to safely access dictionary.

    Note that this function would have negative impact on performance.
    """

    try:
        return func()
    except KeyError:
        return None
        

def isvalid_date(date):
    try:
        dateutil.parser.parse(date)
        return True
    except ValueError:
        return False
        
        
def is_number(s):
    try:
        float(s)
        return True
    except ValueError:
        return False


def build_validation_result(is_valid, is_done, violated_slot, message_content):
    return {
        'isValid': is_valid,
        'isDone': is_done,
        'violatedSlot': violated_slot,
        'message': {'contentType': 'PlainText', 'content': message_content}
    }

""" --- Functions that control the bot's behavior --- """
def getPatientAuth(intent_request):
    """
    Authenticate caller and return FHIR STU3 patient ID for the following query
    """
    logger.debug('intent request: {}'.format(intent_request))
    output_session_attributes = intent_request['currentIntent']['slots'] if intent_request['currentIntent']['slots'] is not None else {}
    telecom = intent_request['sessionAttributes']['telecom'] if intent_request['sessionAttributes']['telecom'] is not None else {}
    logger.debug('phone number before tranformation: {}'.format(telecom))
    telecom = '{0}-{1}-{2}'.format(telecom[-10:-7], telecom[-7:-4], telecom[-4:])
    logger.debug('phone number after tranformation: {}'.format(telecom))
    patientinfo = {
        'birthdate': output_session_attributes['patientBirthday'], 
        'gender': output_session_attributes['patientGender'],
        'telecom': telecom
    }
    r = fhirclient.get_patient(patientinfo)
    output_session_attributes['patientid']=r['response']
    if r['status']==200:
        statusMessage = "Thank you for authenticating"
    else:
        statusMessage = "I'm sorry, I didn't find a patient with that information"
    return close(
        output_session_attributes,
        'Fulfilled',
        {
            'contentType': 'PlainText',
            'content': statusMessage
        }
    )


def getMedHelp(intent_request):
    """
    Retrieve Medication Information for a given patient
    """
    logger.info('intent request: {}'.format(intent_request))
    output_session_attributes = intent_request['sessionAttributes'] if intent_request['sessionAttributes'] is not None else {}
    patientid = output_session_attributes['patientid'] if output_session_attributes['patientid'] is not None else {}
    res = fhirclient.get_meds(patientid)
    logger.debug(res)
    if res['status']==200:
        if type(res['response'])==str:
            outputtext = res['response']
        else:
            outputtext = 'I have found the following medications and instructions for you. '
            for med in res["response"]:
                outputtext += med['medicationReference'] + '. '
                if 'dosage' in med and 'patientInstruction' in med['dosage'][0]:
                    outputtext += 'The dosage for this is the following... ' + med['dosage'][0]['patientInstruction']
                else:
                    outputtext += 'I did not find a dosage for this medication. '
    else:
        outputtext = 'I do not have any medication for you.'
        
    return close(
        output_session_attributes,
        'Fulfilled',
        {
            'contentType': 'PlainText',
            'content': outputtext
        }
    )
   
    
def findFutureAppt(intent_request):
    """
    Find future appointment information for a given patient
    """
    logger.info('intent request: {}'.format(intent_request))
    output_session_attributes = intent_request['sessionAttributes'] if intent_request['sessionAttributes'] is not None else {}
    patientid = output_session_attributes['patientid'] if output_session_attributes['patientid'] is not None else {}
    
    res = fhirclient.get_future_appts(patientid)
    logger.debug(res)
    if res['status']==200:
        if type(res['response'])==str:
            outputtext = res['response']
        else:
            outputtext = 'You have {0} number of future appointments, and {1} number of surgeries'.format(res['response']['Number of appointments'], res['response']['Number of surgeries'])
            for appt in res["response"]['Appointment details']:
                outputtext += 'Date {0}, Time: {1}, in {2} TimeZone; Provider: {3}; Department: {4}; Specialty: {5}'.format(appt['Date'], appt['Time'], appt['TimeZone'], appt['Provider'], appt['Department'], appt['Specialty'])
                outputtext += 'StreetAddress: {0} in {1} City {2} State {3}'.format(appt['StreetAddress'][0], appt['City'], appt['State'], appt['Country'])
    else:
        outputtext = 'You do not have any appointment in the future.'
        
    return close(
        output_session_attributes,
        'Fulfilled',
        {
            'contentType': 'PlainText',
            'content': outputtext
        }
    )


""" --- Intents --- """


def dispatch(intent_request):
    """
    Called when the user specifies an intent for this bot.
    """
    logger.debug (intent_request)
    intent_name = intent_request['currentIntent']['name']

    # Dispatch to your bot's intent handlers
    if intent_name == 'getAppointments':
        return findFutureAppt(intent_request)
    if intent_name == 'getMedication':
        return getMedHelp(intent_request)
    if intent_name == 'authenticateUser':
        return getPatientAuth(intent_request)
    raise Exception('Intent with name ' + intent_name + ' not supported')


""" --- Main handler --- """
def lambda_handler(event, context):
    """
    Route the incoming request based on intent.
    The JSON body of the request is provided in the event slot.
    """
    # By default, treat the user request as coming from the America/New_York time zone.
    os.environ['TZ'] = 'America/New_York'
    time.tzset()
    logger.debug('event.bot.name={}'.format(event['bot']['name']))

    return dispatch(event)
