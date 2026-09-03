import os
import time
while(True):
    print("1. Addition")
    print("2. Subtraktion")
    print("3. Multiplikation")
    print("4. Division")
    print("5. Upphöjt med")
    print("6. Roten ur")
    print("7. Quit")
    val = input("Välj mellan 1-7: ")
    if val == '1':
        nummer1 = float(input("välj nummer 1: "))
        nummer2 = float(input("välj nummer 2: "))
        svar = nummer1 + nummer2
        print(f"Svar: {svar}")
        input("Clicka På ENTER För Att Fortsätta")
        os.system('cls')
    if val == '2':
        nummer1 = float(input("välj nummer 1: "))
        nummer2 = float(input("välj nummer 2: "))
        svar = nummer1 - nummer2
        print(f"Svar: {svar}")
        input("Clicka På ENTER För Att Fortsätta")
        os.system('cls')
    if val == '3':
        nummer1 = float(input("välj nummer 1: "))
        nummer2 = float(input("välj nummer 2: "))
        svar = nummer1 * nummer2
        print(f"Svar: {svar}")
        input("Clicka På ENTER För Att Fortsätta")
        os.system('cls')
        
    if val == '4':
        nummer1 = float(input("välj nummer 1: "))
        nummer2 = float(input("välj nummer 2: "))
        svar = nummer1 / nummer2
        print(f"Svar: {svar}")
        input("Clicka På ENTER För Att Fortsätta")
        os.system('cls')
    if val == '5':
        nummer1 = float(input("välj nummer 1: "))
        nummer2 = float(input("välj nummer 2: "))
        svar = nummer1 ** nummer2
        print(f"Svar: {svar}")
        input("Clicka På ENTER För Att Fortsätta")
        os.system('cls')
    if val == '6':
        nummer1 = float(input("välj nummer 1: "))
        nummer2 = float(input("välj nummer 2: "))
        svar = nummer1 // nummer2
        print(f"Svar: {svar}")
        input("Clicka På ENTER För Att Fortsätta")
        os.system('cls')
    if val == '7':
        break