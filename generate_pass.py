import argparse
import random
import string
import pyperclip

def generar_alfanumerica(N):
    """Genera una contraseña alfanumérica de longitud N."""
    caracteres = string.ascii_letters + string.digits
    return ''.join(random.choice(caracteres) for i in range(N))

def generar_solo_letras(N):
    """Genera una contraseña de solo letras de longitud N."""
    caracteres = string.ascii_letters
    return ''.join(random.choice(caracteres) for i in range(N))

def generar_solo_numeros(N):
    """Genera una contraseña de solo números de longitud N."""
    caracteres = string.digits
    return ''.join(random.choice(caracteres) for i in range(N))

def generar_compleja(N):
    """Genera una contraseña compleja de longitud N."""
    caracteres = string.ascii_letters + string.digits + string.punctuation
    return ''.join(random.choice(caracteres) for i in range(N))

def showHelp():
    print('Usage: access.py [OPTIONS]\n')
    print('Options:')
    print('  --len <INTEGER>        Generate pass with X length.')
    print('  --alfanumeric          Generate alfanumeric pass.')
    print('  --only-letters         Generate only letters pass.')
    print('  --only-numbers         Generate only numbers pass.')
    print('  --complex              Generate complex pass.')

def main():
    
    
    parser = argparse.ArgumentParser(description='Generate and remove passwords.')

    parser.add_argument('--len', default=16, type=int, help='Generate pass with X length.')
    parser.add_argument('--alfanumeric', action='store_true', help='Generate alfanumeric pass.')
    parser.add_argument('--only-letters', action='store_true', help='Generate only letters pass.')
    parser.add_argument('--only-numbers', action='store_true', help='Generate only numbers pass.')
    parser.add_argument('--complex', action='store_true', help='Generate complex pass.')

    args = parser.parse_args()

    if args.only_letters:
        passwd = generar_solo_letras(args.len)
    elif args.only_numbers:
        passwd = generar_solo_numeros(args.len)
    elif args.complex:
        passwd = generar_compleja(args.len)
    elif hasattr(args, 'help') and args.help:
        showHelp()
        return
    else:
        passwd = generar_alfanumerica(args.len)
        

    try:
        pyperclip.copy(passwd)
    except:
        pass
    
    print(passwd)

if __name__ == '__main__':
    main()
    