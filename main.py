from __future__ import print_function

import base64
import os
import tkinter.ttk
import tkinter.messagebox
import tkinter.scrolledtext
import threading

import googleapiclient

import rclick_menu
from email.mime.text import MIMEText

import httplib2
import rfc3339
import sys

import time
from apiclient import discovery
from dateutil.parser import *
from dateutil.rrule import *
from googleapiclient import errors
from oauth2client import client
from oauth2client import tools
from oauth2client.file import Storage

import datepicker
import datetime
import validate_email
import configparser

try:
    # noinspection PyUnresolvedReferences
    import argparse

    flags = argparse.ArgumentParser(parents=[tools.argparser]).parse_args()
except ImportError:
    flags = None

settings_file_path = os.path.join(
    os.path.expanduser('~'), '.vacation_calendar_updater.cfg')
config = configparser.RawConfigParser()

# If modifying these scopes, delete your previously saved credentials
# at ~/.credentials/vacation_calendar_tool.json
SCOPES = 'https://www.googleapis.com/auth/calendar' \
         ' https://www.googleapis.com/auth/gmail.send' \
         ' https://www.googleapis.com/auth/gmail.readonly'
CLIENT_SECRET_FILE = 'client_secret.json'
APPLICATION_NAME = 'Vacation Calendar Tool'


def compat_urlsafe_b64encode(v):
    """A urlsafe b64encode which is compatible with Python 2 and 3.
    Args:
      v: A string to encode.
    Returns:
      The encoded string.
    """
    if sys.version_info[0] >= 3:  # pragma: NO COVER
        return base64.urlsafe_b64encode(v.encode('UTF-8')).decode('ascii')
    else:
        return base64.urlsafe_b64encode(v)


def get_credentials():
    """Gets valid user credentials from storage.

    If nothing has been stored, or if the stored credentials are invalid,
    the OAuth2 flow is completed to obtain the new credentials.

    Returns:
        Credentials, the obtained credential.
    """
    home_dir = os.path.expanduser('~')
    credential_dir = os.path.join(home_dir, '.credentials')
    if not os.path.exists(credential_dir):
        os.makedirs(credential_dir)
    credential_path = os.path.join(credential_dir,
                                   'vacation-calendar-tool.json')

    store = Storage(credential_path)
    retrieved_credentials = store.get()
    if not retrieved_credentials or retrieved_credentials.invalid:
        flow = client.flow_from_clientsecrets(CLIENT_SECRET_FILE, SCOPES)
        flow.user_agent = APPLICATION_NAME
        if flags:
            retrieved_credentials = tools.run_flow(flow, store, flags)
        else:  # Needed only for compatibility with Python 2.6
            retrieved_credentials = tools.run(flow, store)
        print('Storing credentials to ' + credential_path)
    return retrieved_credentials


def create_message(sender, to, subject, message_text):
    """Create a message for an email.

  Args:
    sender: Email address of the sender.
    to: Email address of the receiver.
    subject: The subject of the email message.
    message_text: The text of the email message.

  Returns:
    An object containing a base64url encoded email object.
  """
    message = MIMEText(message_text)
    message['to'] = to
    message['from'] = sender
    message['subject'] = subject
    return {'raw': compat_urlsafe_b64encode(message.as_string())}


def send_message(service, user_id, message):
    """Send an email message.

  Args:
    service: Authorized Gmail API service instance.
    user_id: User's email address. The special value "me"
    can be used to indicate the authenticated user.
    message: Message to be sent.

  Returns:
    Sent Message.
  """
    try:
        message = (service.users().messages().send(userId=user_id, body=message)
                   .execute())
        print('Message Id: %s' % message['id'])
        return message
    except errors.HttpError as error:
        print('An error occurred: %s' % error)


root_window = tkinter.Tk()
root_window.title("Vacation Calendar Updater")
loading_label = tkinter.Label(root_window, text="Loading, Please Wait")
loading_label.pack()
root_window.update()


def start_connection():
    global calendar_service
    global email_service
    credentials = get_credentials()
    http = credentials.authorize(httplib2.Http())
    try:
        calendar_service = discovery.build('calendar', 'v3', http=http)
        email_service = discovery.build('gmail', 'v1', http=http)
    except httplib2.ServerNotFoundError as connection_issue:
        root_window.withdraw()
        tkinter.messagebox.showerror(
            "Unable to connect to server", connection_issue)
        raise SystemExit


start_connection()

event_input_var = tkinter.StringVar()
start_date_selector_var = tkinter.StringVar()
end_date_selector_var = tkinter.StringVar()
start_time_input_var = tkinter.StringVar()
end_time_input_var = tkinter.StringVar()
notification_input_var = tkinter.StringVar()
monday_checkbutton_var = tkinter.BooleanVar()
tuesday_checkbutton_var = tkinter.BooleanVar()
wednesday_checkbutton_var = tkinter.BooleanVar()
thursday_checkbutton_var = tkinter.BooleanVar()
friday_checkbutton_var = tkinter.BooleanVar()
saturday_checkbutton_var = tkinter.BooleanVar()
sunday_checkbutton_var = tkinter.BooleanVar()

check_button_list = []
event_id_list = []

calendar_events_keep_alive = False


def insert_event_into_cal(start_date, end_date):
    calendar_id = get_calendar_id()
    event = {
        'summary': event_input.get(),
        'start': dict(dateTime=start_date),
        'end': dict(dateTime=end_date, ),
        'reminders': dict(useDefault='False')
    }
    event = calendar_service.events().insert(
        calendarId=calendar_id,
        body=event).execute()
    print('Event created: %s' % (event.get('htmlLink')))
    return event['id'], calendar_id


def process_dates():
    global calendar_events_keep_alive
    global event_id_list
    start_connection()
    start_date_list = list(rrule(DAILY, byweekday=tuple(check_button_list),
                                 dtstart=parse(start_date_selector.get(
                                 ) + " " + start_time_input.get()),
                                 until=parse(end_date_selector.get() + " " + start_time_input.get())))

    stop_date_list = list(rrule(DAILY, byweekday=tuple(check_button_list), dtstart=parse(
        start_date_selector.get() + " " + start_time_input.get()) + datetime.timedelta(
        hours=float(end_time_entry.get())),
        until=parse(
        end_date_selector.get() + " " + start_time_input.get()) + datetime.timedelta(
        hours=float(end_time_entry.get()))))

    date_list = zip(start_date_list, stop_date_list)

    hours = 0.0
    days = 0

    event_id_list = []

    try:
        for start, stop in date_list:
            if not calendar_events_keep_alive:
                break
            else:
                event_id_list.append(insert_event_into_cal(
                    rfc3339.rfc3339(start), rfc3339.rfc3339(stop)))
                days += 1
                hours += float(end_time_entry.get())
    except googleapiclient.errors.HttpError:
        root_window.withdraw()
        tkinter.messagebox.showerror("Error Adding Event",
                                     "Error when attempting to create events,\n does the calendar still exist?")
        raise SystemExit
    message_text = "Calendar event(s) created for \"{0}\" event," \
                   " for {1} hours, over the course of {2} days." \
                   " The event days are between {3} and {4}".\
                   format(event_input.get(), str(hours), str(days),
                          str(start_date_selector.get()), str(end_date_selector.get()))
    notify_message = create_message('me',
                                    notification_input.get(),
                                    '{} Calendar Event Created'.format(
                                        event_input.get()),
                                    message_text)
    send_message(email_service, 'me', notify_message)
    print(message_text)


def cancel_adding_events():
    global calendar_events_keep_alive
    calendar_events_keep_alive = False


def undo_events_added():
    global event_id_list
    start_connection()
    event_counter = 0
    try:
        for event_id, calendar_id in event_id_list:
            event_counter += 1
            print("Deleting event with id: " + event_id)
            calendar_service.events().delete(calendarId=calendar_id, eventId=event_id).execute()
            print("Success")
        message_text = "\"{0}\" Calendar event(s) deleted".format(
            str(event_counter))
        notify_message = create_message('me',
                                        notification_input.get(),
                                        'Previous Calendar Event Deleted',
                                        message_text)
        send_message(email_service, 'me', notify_message)
    except googleapiclient.errors.HttpError:
        root_window.withdraw()
        tkinter.messagebox.showerror("Error Removing Event",
                                     "Error when attempting to remove events,\n does the calendar still exist?")
        raise SystemExit
    print(message_text)


def undo_process_dates():
    global event_id_list
    print("Deleting Events")
    event_input.configure(state=tkinter.DISABLED)
    start_date_selector.configure(state=tkinter.DISABLED)
    end_date_selector.configure(state=tkinter.DISABLED)
    process_events_button.configure(state=tkinter.DISABLED)
    select_calendar_menu.configure(state=tkinter.DISABLED)
    undo_process_button.configure(state=tkinter.DISABLED)
    calendar_update_thread_object = threading.Thread(target=undo_events_added)
    calendar_update_thread_object.start()
    while calendar_update_thread_object.is_alive():
        time.sleep(0.1)
        root_window.update()

    event_input.configure(state=tkinter.NORMAL)
    start_date_selector.configure(state=tkinter.NORMAL)
    end_date_selector.configure(state=tkinter.NORMAL)
    process_events_button.configure(state=tkinter.NORMAL)
    select_calendar_menu.configure(state=tkinter.NORMAL)
    set_config_options()
    event_id_list = []
    print("\nDone.\n")


def process_dates_thread_wrapper():
    global calendar_events_keep_alive
    print("Starting new event")
    calendar_events_keep_alive = True
    event_input.configure(state=tkinter.DISABLED)
    start_date_selector.configure(state=tkinter.DISABLED)
    end_date_selector.configure(state=tkinter.DISABLED)
    process_events_button.configure(
        text="Stop Processing", command=cancel_adding_events)
    select_calendar_menu.configure(state=tkinter.DISABLED)
    undo_process_button.configure(state=tkinter.DISABLED)
    calendar_update_thread_object = threading.Thread(target=process_dates)
    calendar_update_thread_object.start()
    while calendar_update_thread_object.is_alive():
        time.sleep(0.1)
        root_window.update()

    event_input.configure(state=tkinter.NORMAL)
    start_date_selector.configure(state=tkinter.NORMAL)
    end_date_selector.configure(state=tkinter.NORMAL)
    process_events_button.configure(
        text="Insert Into Calendar", command=process_dates_thread_wrapper)
    select_calendar_menu.configure(state=tkinter.NORMAL)
    if len(event_id_list) > 0:
        undo_process_button.configure(state=tkinter.NORMAL)
    set_config_options()
    print("\nDone.\n")


class StdoutRedirector(object):
    def __init__(self, text_widget):
        self.text_space = text_widget

    def write(self, string):
        self.text_space.insert('end', string)
        self.text_space.see('end')

    def flush(self):
        pass


def get_calendar_id():
    match_list = next(
        (l for l in calendar_list if l['summary'] == select_calendar_menu_var.get())), None
    for key, value in match_list[0].items():
        if key == 'id':
            return value


def get_number_days():
    start_date_list = list(rrule(DAILY, byweekday=tuple(check_button_list),
                                 dtstart=parse(start_date_selector.get(
                                 ) + " " + start_time_input.get()),
                                 until=parse(end_date_selector.get() + " " + start_time_input.get())))
    return len(start_date_list)


def field_sanity_check():
    global check_button_list
    check_errors = False
    if event_input.get() == "" or event_input.get() is None:
        check_errors = True
    if not validate_email.validate_email(notification_input.get()):
        check_errors = True
    if not len(check_button_list) > 0:
        check_errors = True
    try:
        parse(start_date_selector.get())
        parse(end_date_selector.get())
        parse(start_date_selector.get() + " " + start_time_input.get())
        if not float(end_time_entry.get()) > 0 and not float(end_time_entry.get()) < 24:
            check_errors = True
        if parse(start_date_selector_var.get()) > parse(end_date_selector_var.get()):
            check_errors = True
        if get_number_days() == 0:
            check_errors = True
    except ValueError:
        check_errors = True
    except NameError:
        check_errors = True
    except OverflowError:
        check_errors = True
    return check_errors


def process_events_button_toggle(name=None, index=None, mode=None):
    _ = name, index, mode
    if field_sanity_check():
        process_events_button.configure(state=tkinter.DISABLED)
        try:
            number_days_label.configure(text="check settings")
        except NameError:
            pass
    else:
        process_events_button.configure(state=tkinter.NORMAL)
        number_days_label.configure(text="{} days ({} hours)".format(
            get_number_days(), str(int(get_number_days()) * float(end_time_input_var.get()))))
        set_config_options()
    if len(event_id_list) > 0:
        try:
            undo_process_button.configure(state=tkinter.NORMAL)
        except NameError:
            pass
    else:
        try:
            undo_process_button.configure(state=tkinter.DISABLED)
        except NameError:
            pass


def get_calendar_list():
    page_token = None
    calendar_summary_list = []
    while True:
        calendar_list_from_net = calendar_service.calendarList().list(
            pageToken=page_token).execute()
        for calendar_list_entry in calendar_list_from_net['items']:
            if not calendar_list_entry['accessRole'] == 'reader':
                calendar_summary_list.append(calendar_list_entry['summary'])
        page_token = calendar_list_from_net.get('nextPageToken')
        if not page_token:
            break
    return calendar_summary_list, calendar_list_from_net['items']


user_profile = email_service.users().getProfile(userId='me').execute()
user_email_from_net = user_profile['emailAddress']

filtered_calendar_list, calendar_list = get_calendar_list()
calendar_menu_options = tuple(filtered_calendar_list)


def set_config_to_defaults():
    config.add_section('settings')
    config.set('settings', 'email_address', user_email_from_net)
    config.set('settings', 'calendar', calendar_menu_options[0])
    config.set('settings', 'monday', True)
    config.set('settings', 'tuesday', True)
    config.set('settings', 'wednesday', True)
    config.set('settings', 'thursday', True)
    config.set('settings', 'friday', True)
    config.set('settings', 'saturday', True)
    config.set('settings', 'sunday', True)
    with open(settings_file_path, 'w') as configfile:
        config.write(configfile)


def remove_config_file():
    os.remove(settings_file_path)


if not os.path.exists(settings_file_path):
    set_config_to_defaults()

config.read(settings_file_path)  # open config file


def set_config_options():
    config.set('settings', 'email_address', notification_input.get())
    config.set('settings', 'calendar', select_calendar_menu_var.get())
    config.set('settings', 'monday', monday_checkbutton_var.get())
    config.set('settings', 'tuesday', tuesday_checkbutton_var.get())
    config.set('settings', 'wednesday', wednesday_checkbutton_var.get())
    config.set('settings', 'thursday', thursday_checkbutton_var.get())
    config.set('settings', 'friday', friday_checkbutton_var.get())
    config.set('settings', 'saturday', saturday_checkbutton_var.get())
    config.set('settings', 'sunday', sunday_checkbutton_var.get())
    with open(settings_file_path, 'w') as configfile:
        config.write(configfile)


config_issues = False

try:
    _ = config.get('settings', 'email_address')
    _ = config.get('settings', 'calendar')
    _ = config.getboolean('settings', 'monday')
    _ = config.getboolean('settings', 'tuesday')
    _ = config.getboolean('settings', 'wednesday')
    _ = config.getboolean('settings', 'thursday')
    _ = config.getboolean('settings', 'friday')
    _ = config.getboolean('settings', 'saturday')
    _ = config.getboolean('settings', 'sunday')
except KeyError:
    config_issues = True
except configparser.NoOptionError:
    config_issues = True
except configparser.NoSectionError:
    config_issues = True
if config_issues:
    config = configparser.RawConfigParser()
    remove_config_file()
    set_config_to_defaults()
    config.read(settings_file_path)
    config_issues = False

config.read(settings_file_path)
user_email = config.get('settings', 'email_address')
default_calendar = config.get('settings', 'calendar')

if not validate_email.validate_email(user_email) or default_calendar not in calendar_menu_options:
    config = None
    remove_config_file()
    set_config_to_defaults()
    config.read(settings_file_path)

loading_label.destroy()

process_events_button = tkinter.Button(
    root_window, text="Insert Into Calendar", command=process_dates_thread_wrapper)

process_events_button.grid(row=4, column=0, columnspan=2, sticky=tkinter.N)

undo_process_button = tkinter.Button(
    root_window, text="Undo", command=undo_process_dates)

undo_process_button.grid(row=4, column=1, columnspan=2, sticky=tkinter.N)

event_input_var.trace('w', callback=process_events_button_toggle)
start_date_selector_var.trace('w', callback=process_events_button_toggle)
end_date_selector_var.trace('w', callback=process_events_button_toggle)
start_time_input_var.trace('w', callback=process_events_button_toggle)
end_time_input_var.trace('w', callback=process_events_button_toggle)
notification_input_var.trace('w', callback=process_events_button_toggle)

notification_email_label = tkinter.Label(
    root_window, text="Notification Email").grid(row=0, column=2)
notification_input = tkinter.Entry(
    root_window, textvariable=notification_input_var)
notification_input.grid(row=0, column=3, sticky=tkinter.E + tkinter.W)
notification_input_rclick_menu = rclick_menu.RightClickMenu(notification_input)
notification_input.bind("<3>", notification_input_rclick_menu)

event_input_label = tkinter.Label(
    root_window, text="Event Name").grid(row=0, column=0)
event_input = tkinter.Entry(root_window, textvariable=event_input_var)
event_input.grid(row=0, column=1, sticky=tkinter.E + tkinter.W)
event_input_rclick_menu = rclick_menu.RightClickMenu(event_input)
event_input.bind("<3>", event_input_rclick_menu)

start_date_selector_label = tkinter.Label(
    root_window, text="Start Date").grid(row=1, column=0)
start_date_selector = datepicker.Datepicker(
    root_window, datevar=start_date_selector_var)
start_date_selector.grid(row=1, column=1, sticky=tkinter.E + tkinter.W)
start_date_selector_rclick_menu = rclick_menu.RightClickMenu(
    start_date_selector)
start_date_selector.bind("<3>", start_date_selector_rclick_menu)

start_time_input = tkinter.Entry(
    root_window, textvariable=start_time_input_var)
start_time_input.grid(row=1, column=3, sticky=tkinter.E + tkinter.W)
start_time_label = tkinter.Label(root_window, text="Start Time")
start_time_label.grid(row=1, column=2)

end_date_selector_label = tkinter.Label(
    root_window, text="End Date").grid(row=2, column=0)
end_date_selector = datepicker.Datepicker(
    root_window, datevar=end_date_selector_var)
end_date_selector.grid(row=2, column=1, sticky=tkinter.E + tkinter.W)
end_date_selector_rclick_menu = rclick_menu.RightClickMenu(end_date_selector)
end_date_selector.bind("<3>", end_date_selector_rclick_menu)

end_time_label = tkinter.Label(root_window, text="Day Length")
end_time_label.grid(row=2, column=2)
end_time_entry = tkinter.Spinbox(root_window, from_=0, to=24, increment=.25, format='%.2f',
                                 textvariable=end_time_input_var)
end_time_entry.grid(row=2, column=3, sticky=tkinter.E + tkinter.W)

weekday_frame = tkinter.Frame(root_window)


def checkbutton_state_list():
    global check_button_list
    check_button_list = []
    if monday_checkbutton_var.get():
        check_button_list.append(MO)
    if tuesday_checkbutton_var.get():
        check_button_list.append(TU)
    if wednesday_checkbutton_var.get():
        check_button_list.append(WE)
    if thursday_checkbutton_var.get():
        check_button_list.append(TH)
    if friday_checkbutton_var.get():
        check_button_list.append(FR)
    if saturday_checkbutton_var.get():
        check_button_list.append(SA)
    if sunday_checkbutton_var.get():
        check_button_list.append(SU)
    process_events_button_toggle()


monday_checkbutton = tkinter.Checkbutton(weekday_frame, text="MO", indicatoron=tkinter.FALSE,
                                         var=monday_checkbutton_var,
                                         command=checkbutton_state_list, onvalue=True, offvalue=False)
monday_checkbutton.grid(row=0, column=0, sticky=tkinter.W + tkinter.E)

tuesday_checkbutton = tkinter.Checkbutton(weekday_frame, text="TU", indicatoron=tkinter.FALSE,
                                          var=tuesday_checkbutton_var,
                                          command=checkbutton_state_list, onvalue=True, offvalue=False)
tuesday_checkbutton.grid(row=0, column=1, sticky=tkinter.W + tkinter.E)

wednesday_checkbutton = tkinter.Checkbutton(weekday_frame, text="WE", indicatoron=tkinter.FALSE,
                                            var=wednesday_checkbutton_var,
                                            command=checkbutton_state_list, onvalue=True, offvalue=False)
wednesday_checkbutton.grid(row=0, column=2, sticky=tkinter.W + tkinter.E)

thursday_checkbutton = tkinter.Checkbutton(weekday_frame, text="TH", indicatoron=tkinter.FALSE,
                                           var=thursday_checkbutton_var,
                                           command=checkbutton_state_list, onvalue=True, offvalue=False)
thursday_checkbutton.grid(row=0, column=3, sticky=tkinter.W + tkinter.E)

friday_checkbutton = tkinter.Checkbutton(weekday_frame, text="FR", indicatoron=tkinter.FALSE,
                                         var=friday_checkbutton_var,
                                         command=checkbutton_state_list, onvalue=True, offvalue=False)
friday_checkbutton.grid(row=0, column=4, sticky=tkinter.W + tkinter.E)

saturday_checkbutton = tkinter.Checkbutton(weekday_frame, text="SA", indicatoron=tkinter.FALSE,
                                           var=saturday_checkbutton_var,
                                           command=checkbutton_state_list, onvalue=True, offvalue=False)
saturday_checkbutton.grid(row=0, column=5, sticky=tkinter.W + tkinter.E)

sunday_checkbutton = tkinter.Checkbutton(weekday_frame, text="SU", indicatoron=tkinter.FALSE,
                                         var=sunday_checkbutton_var,
                                         command=checkbutton_state_list, onvalue=True, offvalue=False)
sunday_checkbutton.grid(row=0, column=6, sticky=tkinter.W + tkinter.E)

monday_checkbutton_var.set(config.get('settings', 'monday'))
tuesday_checkbutton_var.set(config.get('settings', 'tuesday'))
wednesday_checkbutton_var.set(config.get('settings', 'wednesday'))
thursday_checkbutton_var.set(config.get('settings', 'thursday'))
friday_checkbutton_var.set(config.get('settings', 'friday'))
saturday_checkbutton_var.set(config.get('settings', 'saturday'))
sunday_checkbutton_var.set(config.get('settings', 'sunday'))

checkbutton_state_list()

weekday_frame.grid(row=3, column=0, columnspan=2, pady=4)

number_days_label = tkinter.ttk.Label(master=root_window)

number_days_label.grid(row=3, column=2, columnspan=2)

select_calendar_menu_var = tkinter.StringVar()
select_calendar_menu_var.set(default_calendar)
select_calendar_menu = tkinter.ttk.OptionMenu(root_window, select_calendar_menu_var, default_calendar,
                                              *calendar_menu_options)

select_calendar_menu.grid(row=4, column=2, columnspan=2, sticky=tkinter.N)
log_text_box = tkinter.scrolledtext.ScrolledText(
    master=root_window, wrap='word', height=10, width=50)
log_text_box.grid(row=5, column=0, columnspan=4, padx=5, pady=5,
                  sticky=tkinter.N + tkinter.S + tkinter.E + tkinter.W)
log_text_box.rowconfigure(5, weight=1)
root_window.rowconfigure(4, weight=1)
root_window.columnconfigure(1, weight=1)
root_window.columnconfigure(3, weight=1)
root_window.update()
root_window.minsize(width=root_window.winfo_width(),
                    height=root_window.winfo_height())
root_window.resizable(height=False, width=False)
sys.stdout = StdoutRedirector(log_text_box)
log_text_box.bind("<Key>", lambda e: "break")

notification_input.delete(0, "end")
notification_input.insert(0, user_email)
start_time_input.delete(0, "end")
start_time_input.insert(0, "0800")
end_time_entry.delete(0, "end")
end_time_entry.insert(0, 8.00)
process_events_button_toggle()

print("Ready to start.\nPlease insert Event Name, Start Date and, End Date.")

root_window.mainloop()
