#!/usr/bin/python3

# Importing Netmiko modules
from netmiko import Netmiko
from netmiko.ssh_exception import NetMikoAuthenticationException, NetMikoTimeoutException

# Additional modules imported for getting password, pretty print
from getpass import getpass
from pprint import pprint
import signal,os,sys

# Queuing and threading libraries
from queue import Queue
import threading

# These capture errors relating to hitting ctrl+C
signal.signal(signal.SIGPIPE, signal.SIG_DFL)  # IOError: Broken pipe
signal.signal(signal.SIGINT, signal.SIG_DFL)  # KeyboardInterrupt: Ctrl-C

# Get the credentials
username = input("Username: ")
password = getpass("Password: ")

# Switch IP addresses from text file that has one IP per line
ip_addrs_file = open('ips.txt')
ip_addrs = ip_addrs_file.read().splitlines()

# Open the output file that will have ip,serial format per line. This WILL overwrite the file if it already exists!
serial_outputfile = open('serials.txt', 'w')

# Set up thread count for number of threads to spin up.
num_threads = 8

# This sets up the queue
enclosure_queue = Queue()

# Set up thread lock so that only one thread prints at a time
print_lock = threading.Lock()

# CLI command being sent
command = "show inventory"

# Cosmetic print
print("*** Script starting ***")

# Function used in threads to connect to devices, passing in the thread # and queue
def deviceconnector(i,q):

    # This while loop runs indefinitely and grabs IP addresses from the queue and processes them
    # Loop will be blocked and wait if "ip = q.get()" is empty
    while True:
        
        ip = q.get()
        print("{}: Acquired IP: {}".format(i,ip))
        
        # k,v passed to net_connect
        device_dict =  {
            'host': ip,
            'username': username,
            'password': password,
            'device_type': 'cisco_asa'
        }

        # Connect to the device, and print out auth or timeout errors
        try:
            net_connect = Netmiko(**device_dict)
        except NetMikoTimeoutException:
            with print_lock:
                print("\n{}: ERROR: Connection to {} timed-out.\n".format(i,ip))
            q.task_done()
            continue
        except NetMikoAuthenticationException:
            with print_lock:
                print("\n{}: ERROR: Authentication failed for {}. Stopping thread. \n".format(i,ip))
            q.task_done()
            os.kill(os.getpid(), signal.SIGUSR1)

        # Capture the output, and use TextFSM to parse data
        output = net_connect.send_command(command,use_textfsm=True)
        
        with print_lock:

            sn = output[0]
            sn = sn["sn"]
            serial_outputfile.write(ip + "," + sn + "\n")

        # Disconnect from device
        net_connect.disconnect

        # Set the queue task as complete, thereby removing it from the queue indefinitely
        q.task_done()

def main():

    # Setting up threads based on number set above
    for i in range(num_threads):
        # Create the thread using 'deviceconnector' as the function, passing in
        # the thread number and queue object as parameters 
        thread = threading.Thread(target=deviceconnector, args=(i,enclosure_queue,))
        # Set the thread as a background daemon/job
        thread.setDaemon(True)
        # Start the thread
        thread.start()

    # For each ip address in "ip_addrs", add that IP address to the queue
    for ip_addr in ip_addrs:
        enclosure_queue.put(ip_addr)

    # Wait for all tasks in the queue to be marked as completed (task_done)
    enclosure_queue.join()
    serial_outputfile.close()
    print("*** Script complete ***")

if __name__ == '__main__':
    
    # Calling the main function
    main()