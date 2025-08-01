#!/usr/bin/env python3
"""
Convert your custom icon to ICO and ICNS formats
"""
from PIL import Image
import os

def process_custom_icon(input_path):
    """Process your custom icon image"""
    
    # Load your image
    try:
        img = Image.open(input_path)
        print(f"✓ Loaded {input_path} - Size: {img.size}, Mode: {img.mode}")
    except Exception as e:
        print(f"✗ Error loading image: {e}")
        return None
    
    # Convert to RGBA if not already (for transparency support)
    if img.mode != 'RGBA':
        img = img.convert('RGBA')
        print("✓ Converted to RGBA mode for transparency support")
    
    # Optional: Make white background transparent
    # Uncomment the lines below if you want to remove white background
    """
    data = img.getdata()
    new_data = []
    for item in data:
        # Change all white (also shades of whites) pixels to transparent
        if item[0] > 200 and item[1] > 200 and item[2] > 200:
            new_data.append((255, 255, 255, 0))  # Transparent
        else:
            new_data.append(item)
    img.putdata(new_data)
    print("✓ Made white background transparent")
    """
    
    # Resize to optimal size if needed
    target_size = 1024
    if img.size[0] != target_size or img.size[1] != target_size:
        img = img.resize((target_size, target_size), Image.Resampling.LANCZOS)
        print(f"✓ Resized to {target_size}×{target_size}")
    
    return img

def create_icons_from_custom(icon_img):
    """Create ICO and ICNS from your custom icon"""
    
    # Save master PNG
    icon_img.save('icon.png')
    print("✓ Saved icon.png")
    
    # Windows ICO - multiple sizes
    windows_sizes = [(16,16), (24,24), (32,32), (48,48), (64,64), (128,128), (256,256), (512,512)]
    try:
        icon_img.save('icon.ico', format='ICO', sizes=windows_sizes)
        print("✓ Created icon.ico with all Windows sizes")
    except Exception as e:
        print(f"✗ Error creating ICO: {e}")
        # Try with fewer sizes
        icon_img.save('icon.ico', format='ICO', sizes=[(16,16), (32,32), (48,48), (128,128), (256,256)])
        print("✓ Created icon.ico (fallback)")
    
    # macOS iconset
    iconset_dir = "icon.iconset"
    if not os.path.exists(iconset_dir):
        os.makedirs(iconset_dir)
    
    # Create all required macOS sizes
    macos_files = [
        (16, "icon_16x16.png"),
        (32, "icon_16x16@2x.png"),
        (32, "icon_32x32.png"), 
        (64, "icon_32x32@2x.png"),
        (128, "icon_128x128.png"),
        (256, "icon_128x128@2x.png"),
        (256, "icon_256x256.png"),
        (512, "icon_256x256@2x.png"),
        (512, "icon_512x512.png"),
        (1024, "icon_512x512@2x.png")
    ]
    
    for size, filename in macos_files:
        resized = icon_img.resize((size, size), Image.Resampling.LANCZOS)
        resized.save(os.path.join(iconset_dir, filename))
    
    print(f"✓ Created {iconset_dir}/ with all macOS sizes")
    
    # Try to create ICNS on macOS
    if os.name == 'posix':
        try:
            import subprocess
            result = subprocess.run(['iconutil', '-c', 'icns', iconset_dir, '-o', 'icon.icns'], 
                                  capture_output=True, text=True)
            if result.returncode == 0:
                print("✓ Created icon.icns using iconutil")
            else:
                print("! iconutil not available - convert manually")
        except:
            print("! iconutil not available - convert manually")
    
    return True

def main():
    """Main function"""
    print("Custom Icon Converter for Pipeline Calculator")
    print("=" * 50)
    
    # Look for your icon file (adjust the filename as needed)
    possible_names = [
        'your_icon.png',
        'custom_icon.png', 
        'source_icon.png',
        'icon_source.png'
    ]
    
    input_file = None
    for name in possible_names:
        if os.path.exists(name):
            input_file = name
            break
    
    if not input_file:
        print("Please save your icon as 'custom_icon.png' in this directory")
        print("Or modify this script to point to your icon file")
        return
    
    # Process the icon
    processed_icon = process_custom_icon(input_file)
    if processed_icon:
        create_icons_from_custom(processed_icon)
        
        print("\n" + "=" * 50)
        print("SUCCESS! Created:")
        print("✓ icon.png - Master file") 
        print("✓ icon.ico - Windows icon")
        print("✓ icon.iconset/ - macOS source files")
        if os.path.exists('icon.icns'):
            print("✓ icon.icns - macOS icon")
        else:
            print("! icon.icns - Create manually with:")
            print("  iconutil -c icns icon.iconset -o icon.icns")
            print("  or use https://iconverticons.com/online/")
        
        print("\nNext steps:")
        print("1. Delete the icon folders from your repo")
        print("2. Add icon.ico and icon.icns to repo root") 
        print("3. Update build.yml to include --icon parameters")

if __name__ == "__main__":
    try:
        from PIL import Image
        main()
    except ImportError:
        print("Please install Pillow: pip install Pillow")