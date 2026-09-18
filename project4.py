import random
import os
import time
class player:
    def __init__(self, namn, poäng=0):
        self.namn = namn
        self.poäng = poäng
        self.runda = 0
        self.poäng = 0
        pass
    def __str__(self):
        return self.namn
        pass
    def kasta(resultat):
        return random.randint(1, 6)
        pass
    def vann(self):
        return self.poäng + 1
        pass
os.system('cls')
print("--------------------------------")
print("Välkommen till dice battles!!")
namn1 = input("\033[1;32mSpelare 1 välj ett namn: \033[0m")
player1 = player(namn1)
print("Välkommen", player1)
namn2 = input("\033[1;34mSpelare 2 välj ett namn: \033[0m")
player2 = player(namn2)
print("Välkommen", player2)
input("\033[1;31mÄr ni redo? Clicka enter för att gå vidare\033[0m")
print("--------------------------------")
time.sleep(2)
os.system('cls')
while(True):
    player1.runda += 1
    print("runda", player1.runda)
    print(player1)
    input("Clicka ENTER för att kasta")
    time.sleep(1)
    resultat = player1.kasta()
    print(player1, "Du fick", resultat)
    time.sleep(2)
    os.system('cls')
    print(player2)
    input("Clicka ENTER för att kasta")
    time.sleep(1)
    resultat2 = player2.kasta()
    print(player2, "Du fick", resultat2)
    time.sleep(2)
    os.system('cls')
    if resultat >= resultat2:
        print(("\033[1;32mSpelare 1 vann!! \033[0m"))
        player1.vann()
        time.sleep(2)
    elif resultat2 >= resultat:
        print(("\033[1;32mSpelare 2 vann!! \033[0m"))
        player2.vann()
    time.sleep(2)
    if player1.poäng == '5':
        print(player.namn, "\033[1;32mVann hela skiten!! \033[0m")
        break








