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


""" --- Functions that control the bot's behavior --- """
def getPatientAuth(intent_request):
    """
    Authenticate caller and return FHIR STU3 patient ID for the following query
    """
    logger.debug('intent request: {}'.format(intent_request))
    output_session_attributes = intent_request['currentIntent']['slots'] if intent_request['currentIntent']['slots'] is not None else {}
    telecom = intent_request['sessionAttributes']['telecom'] if intent_request['sessionAttributes']['telecom'] is not None else {}
    
    ## format phone number
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
