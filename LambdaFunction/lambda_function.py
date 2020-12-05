import json, random, string, os, math, time, datetime, dateutil.parser
from pprint import pprint
import boto3
from datetime import datetime, timedelta, timezone
import jwt
import requests
from hl7.xml import parse
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
def getmedhelp(intent_request):
    patientid = intent_request['sessionAttributes']['patientid'] if intent_request['sessionAttributes']['patientid'] is not None else {}
    meds = fhirclient.get_meds(patientid)
    logger.info(meds)
    output_session_attributes['patientid'] = ''
    
    outputtext = 'I have found the following medications and instructions for you. '
    
    for i in meds["medications"]:
        med = json.loads(i)
        
        outputtext += med['medicationReference'] + '. '
        if 'dosage' in med:
            outputtext += 'The dosage for this is the following... ' + med['dosage']
        else:
            outputtext += 'I did not find a dosage for this medication. '
    
    return close(
        output_session_attributes,
        'Fulfilled',
        {
            'contentType': 'PlainText',
            'content': outputtext
        }
    )
    
def getPatientAuth(intent_request):
    output_session_attributes = intent_request['currentIntent']['slots'] if intent_request['currentIntent']['slots'] is not None else {}
    telecom = intent_request['sessionAttributes']['telecom'] if intent_request['sessionAttributes']['telecom'] is not None else {}
    print(telecom)
    telecom = '{0}-{1}-{2}'.format(telecom[-10:-7], telecom[-7:-4], telecom[-4:])
    print(telecom)
    print(intent_request)
    print(output_session_attributes)
    patientinfo = {
        'birthdate': output_session_attributes['patientBirthday'], 
        'gender': output_session_attributes['patientGender'],
        'telecom': telecom
    }
    r = fhirclient.get_patient(patientinfo)
    output_session_attributes['patientid']=r['patientid']
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
   
    
def find_appt(intent_request):
    """
    Performs dialog management and fulfillment for scheduling an appointment.
    """
    
    patientinfo = {
        'family': 'Mychart', 
        'given': 'Allison',
        'gender': 'Female',
        'telecom': '608-123-4567'
    }
    r = fhirclient.get_patient(patientinfo)
   
    
    specialty = intent_request['currentIntent']['slots']['specialty']
    apptdate = intent_request['currentIntent']['slots']['apptdate']
    #firstname = intent_request['currentIntent']['slots']['firstname']
    #lastname = intent_request['currentIntent']['slots']['lastname']
    #dob = intent_request['currentIntent']['slots']['dob']
    #phone = intent_request['currentIntent']['slots']['phone']
    #insurance = intent_request['currentIntent']['slots']['insurance']
    #providername = intent_request['currentIntent']['slots']['providername']
    #callername = intent_request['currentIntent']['slots']['callername']
    
    source = intent_request['invocationSource']
    output_session_attributes = intent_request['sessionAttributes'] if intent_request['sessionAttributes'] is not None else {}

    output_session_attributes['patientid'] = r['patientid']
            
    if source == 'DialogCodeHook':
        # Perform basic validation on the supplied input slots.
        slots = intent_request['currentIntent']['slots']
    yesnobuttons = [
                        {'text': 'Yes', 'value': 'Yes'},
                        {'text': 'No', 'value': 'No'}
                    ]
    
    patientcontext = 'the patient'
    """    
    if not specialty:
        return elicit_slot(
            output_session_attributes,
            intent_request['currentIntent']['name'],
            intent_request['currentIntent']['slots'],
            'specialty',
            {'contentType': 'PlainText', 'content': 'What specialty do you need?'},
            build_response_card(
                'Specialty', 'What specialty do you need?',
                ['']
            )
        )
    """    
    if not apptdate:
        return elicit_slot(
            output_session_attributes,
            intent_request['currentIntent']['name'],
            intent_request['currentIntent']['slots'],
            'apptdate',
            {'contentType': 'PlainText', 'content': 'What date would you like an appointment for?'},
            build_response_card(
                'Appointment Date', 'What date would you like an appointment for?',
                ['']
            )
        )
        
    #Call Epic to get dates and reply back with available appt slots
    datetime_object = datetime.strptime(apptdate + ' 8:00AM', '%Y-%m-%d %I:%M%p')
    logger.info('Looking for appt on ' + apptdate)
    appt = find_appointments(datetime_object)
    booked = book_appointments(r['patientid'], appt['appointments'])
    logger.info(booked)
   
    responsetext = 'I have booked a ' + booked['response']['serviceType'] + ' for you on that day.'
    """        
    if not firstname:
        return elicit_slot(
            output_session_attributes,
            intent_request['currentIntent']['name'],
            intent_request['currentIntent']['slots'],
            'firstname',
            {'contentType': 'PlainText', 'content': 'What is ' + patientcontext + ' first name?'},
            build_response_card(
                'Last Name', 'What is ' + patientcontext + ' first name?',
                ['']
            )
        )
 
    if not lastname:
        return elicit_slot(
            output_session_attributes,
            intent_request['currentIntent']['name'],
            intent_request['currentIntent']['slots'],
            'lastname',
            {'contentType': 'PlainText', 'content': 'What is ' + patientcontext + ' last name?'},
            build_response_card(
                'Last Name', 'What is ' + patientcontext + ' last name?',
                ['']
            )
        )

    if not dob:
        return elicit_slot(
            output_session_attributes,
            intent_request['currentIntent']['name'],
            intent_request['currentIntent']['slots'],
            'dob',
            {'contentType': 'PlainText', 'content': 'What is ' + patientcontext + ' date of birth?'},
            build_response_card(
                'Date of birth', 'What is ' + patientcontext + ' date of birth?',
                ['']
            )
        )
        
    if not phone:
        return elicit_slot(
            output_session_attributes,
            intent_request['currentIntent']['name'],
            intent_request['currentIntent']['slots'],
            'phone',
            {'contentType': 'PlainText', 'content': 'What is ' + patientcontext + ' phone number?'},
            build_response_card(
                'Phone', 'What is ' + patientcontext + ' phone number?',
                ['']
            )
        )
        
    if not insurance:
        return elicit_slot(
            output_session_attributes,
            intent_request['currentIntent']['name'],
            intent_request['currentIntent']['slots'],
            'insurance',
            {'contentType': 'PlainText', 'content': 'What is ' + patientcontext + ' insurance company?'},
            build_response_card(
                'Insurance', 'What is ' + patientcontext + ' company?',
                ['']
            )
        )

     """

    #Before scheduling, set value to inform Connect contact flow if this is a patient schedule appointment so we can put them through screening questions

    output_session_attributes['apptdetails'] = 'something here about the appointment'
        
    return close(
        output_session_attributes,
        'Fulfilled',
        {
            'contentType': 'PlainText',
            'content': responsetext
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
    if intent_name == 'FindAppointment':
        return find_appt(intent_request)
    if intent_name == 'MedHelp':
        return getmedhelp(intent_request)
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
