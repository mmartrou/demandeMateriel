from PIL import Image
import os

# Chemins
src = os.path.join('imagesDemandesMateriel', 'profil.png')
dst = os.path.join('static', 'favicon.ico')

# Ouvre l'image source
img = Image.open(src)

# Convertit en carré et redimensionne (32x32 recommandé pour favicon)
img = img.convert('RGBA')
size = (32, 32)
img = img.resize(size, Image.LANCZOS)

# Sauvegarde au format .ico
img.save(dst, format='ICO')
print(f'Favicon créée : {dst}')
