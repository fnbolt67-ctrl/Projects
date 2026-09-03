from itertools import product
import os
import time
chars = '0123456789'
password = input("Välj lösenord: ")

for length in range(1, 5):
    guesses = product(chars, repeat=length)

    for attempt in guesses:
        attempt = ''.join(attempt)
        if attempt == password:
            time.sleep(1)
            print(attempt)
            print("Password found!")
            
            break
