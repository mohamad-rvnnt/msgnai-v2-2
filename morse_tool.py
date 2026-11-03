#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
✨ Morse Code CLI Tool ✨
Author / Creator: @m_sgn
Description: A colorful, emoji-rich terminal utility to encode text to Morse code and decode Morse code to text.
"""

import sys
import os

# Morse Code Dictionary
MORSE_CODE_DICT = {
    'A': '.-', 'B': '-...', 'C': '-.-.', 'D': '-..', 'E': '.',
    'F': '..-.', 'G': '--.', 'H': '....', 'I': '..', 'J': '.---',
    'K': '-.-', 'L': '.-..', 'M': '--', 'N': '-.', 'O': '---',
    'P': '.--.', 'Q': '--.-', 'R': '.-.', 'S': '...', 'T': '-',
    'U': '..-', 'V': '...-', 'W': '.--', 'X': '-..-', 'Y': '-.--',
    'Z': '--..',
    '1': '.----', '2': '..---', '3': '...--', '4': '....-', '5': '.....',
    '6': '-....', '7': '--...', '8': '---..', '9': '----.', '0': '-----',
    ',': '--..--', '.': '.-.-.-', '?': '..--..', '/': '-..-.',
    '-': '-....-', '(': '-.--.', ')': '-.--.-', ' ': '/'
}

# Reverse Dictionary for Decoding
REVERSE_MORSE_DICT = {v: k for k, v in MORSE_CODE_DICT.items()}

# ANSI Colors
CYAN = "\033[96m"
GREEN = "\033[92m"
YELLOW = "\033[93m"
MAGENTA = "\033[95m"
RED = "\033[91m"
BOLD = "\033[1m"
RESET = "\033[0m"

def clear_screen():
    os.system('cls' if os.name == 'nt' else 'clear')

def print_banner():
    clear_screen()
    print(f"{CYAN}{BOLD}")
    print("╔══════════════════════════════════════════════════════════╗")
    print("║                 ✨ MORSE CODE CLI TOOL ✨                ║")
    print("║               Developed by: @m_sgn 🚀                    ║")
    print("╚══════════════════════════════════════════════════════════╝")
    print(f"{RESET}")

def text_to_morse(text):
    text = text.upper()
    morse_result = []
    for char in text:
        if char in MORSE_CODE_DICT:
            morse_result.append(MORSE_CODE_DICT[char])
        else:
            morse_result.append(char) # Keep unknown chars as is
    return ' '.join(morse_result)

def morse_to_text(morse_code):
    words = morse_code.split(' / ')
    decoded_words = []
    for word in words:
        chars = word.split()
        decoded_chars = []
        for char in chars:
            if char in REVERSE_MORSE_DICT:
                decoded_chars.append(REVERSE_MORSE_DICT[char])
            else:
                decoded_chars.append('?')
        decoded_words.append(''.join(decoded_chars))
    return ' '.join(decoded_words)

def interactive_menu():
    while True:
        print_banner()
        print(f"{YELLOW}📌 لطفاً یکی از گزینه‌های زیر را انتخاب کنید:{RESET}\n")
        print(f"  {GREEN}[1]{RESET} 🔤 تبدیل متن (Text) به کد مورس (Morse)")
        print(f"  {GREEN}[2]{RESET} 📡 تبدیل کد مورس (Morse) به متن (Text)")
        print(f"  {RED}[3]{RESET} ❌ خروج از برنامه\n")
        
        choice = input(f"{MAGENTA}👉 لطفاً گزینه مورد نظر را وارد کنید (1/2/3): {RESET}").strip()
        
        if choice == '1':
            print_banner()
            print(f"{CYAN}💬 حالت: تبدیل متن به مورس{RESET}\n")
            user_text = input(f"{YELLOW}✍️ متن خود را وارد کنید: {RESET}")
            if user_text.lower() == 'back':
                continue
            result = text_to_morse(user_text)
            print(f"\n{GREEN}✨ نتیجه مورس:{RESET}\n{BOLD}{result}{RESET}\n")
            input(f"{MAGENTA}⏎ برای بازگشت به منو اینتر بزنید...{RESET}")
            
        elif choice == '2':
            print_banner()
            print(f"{CYAN}💬 حالت: تبدیل مورس به متن{RESET}\n")
            print(f"{YELLOW}💡 راهنمایی: کلمات را با ' / ' و حروف را با فاصله جدا کنید.{RESET}")
            user_morse = input(f"{YELLOW}📡 کد مورس خود را وارد کنید: {RESET}")
            if user_morse.lower() == 'back':
                continue
            result = morse_to_text(user_morse)
            print(f"\n{GREEN}✨ نتیجه متنی:{RESET}\n{BOLD}{result}{RESET}\n")
            input(f"{MAGENTA}⏎ برای بازگشت به منو اینتر بزنید...{RESET}")
            
        elif choice == '3':
            print_banner()
            print(f"{CYAN}👋 از اینکه از ابزار مورس ساخت @m_sgn استفاده کردید سپاسگزاریم! موفق باشید. 🌟{RESET}\n")
            sys.exit(0)
        else:
            print(f"\n{RED}❌ گزینه نامعتبر! لطفاً دوباره تلاش کنید.{RESET}")
            input(f"{MAGENTA}⏎ برای ادامه اینتر بزنید...{RESET}")

if __name__ == '__main__':
    interactive_menu()
