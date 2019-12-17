import time

from toptica.lasersdk.client import Client, SerialConnection, DecopError


def my_callback(timestamp, name, value, exc):
    if exc:
        print('Error occurred!')
        return

    print('--------------------------------------')
    print('Timestamp: ', timestamp)
    print('     Name: ', name)
    print('    Value: ', value)
    print('--------------------------------------')


def main():
    with Client(SerialConnection('COM9')) as client:
        print("This is a '{}' with serial number '{}.'".format(
            client.get('system-type', str),
            client.get('serial-number', str)))

        client.exec('laser1:dl:lock:close')

#        try:
#            client.exec('laser1:dl:lock:close')
#        except DecopError as error:
#            print(error)
      #  client.subscribe('laser1:dl:pressure-compensation:enabled', bool, my_callback)
        #client.set('laser1:dl:pressure-compensation:enabled', True)

        time.sleep(1)


if __name__ == "__main__":
    main()