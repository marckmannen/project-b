import qrcode
import random 
# Generate a random 4-digit number (0000–9999)
random_number = f"{random.randint(0, 9999):04d}"

# Create QR code
img = qrcode.make(random_number)

filename = f"the-amazingcode-is{random_number}.png"
img.save(filename)

print("Number:", random_number)
print("Saved:", filename)
