import sys
from pathlib import Path
from PIL import Image

def pixelate(image_path, output_path, pixel_size=10):
    """Apply a pixelation effect to an image."""
    try:
        with Image.open(image_path) as img:
            # Resize the image to a smaller size
            small_img = img.resize(
                (max(1, img.size[0] // pixel_size), max(1, img.size[1] // pixel_size)),
                Image.NEAREST
            )
            # Scale it back to the original size
            pixelated_img = small_img.resize(img.size, Image.NEAREST)
            # Save the pixelated image
            output_path.parent.mkdir(parents=True, exist_ok=True)  # Ensure directory exists
            pixelated_img.save(output_path)
            print(f"Processed: {image_path} -> {output_path}")
    except Exception as e:
        print(f"ERROR: Failed to process {image_path}: {e}")

def process_images(input_dir, output_dir, pixel_size=10):
    """Process all images in the input directory and its subdirectories."""
    input_path = Path(input_dir)
    output_path = Path(output_dir)

    if not input_path.exists():
        print(f"Input directory does not exist: {input_path}")
        sys.exit(1)

    print(f"DEBUG: Scanning directory {input_dir} for image files...")
    for image_file in input_path.rglob("*"):
        if image_file.suffix.lower() in {".png", ".jpg", ".jpeg"}:
            relative_path = image_file.relative_to(input_path)  # Preserve directory structure
            output_file = output_path / relative_path
            print(f"DEBUG: Processing image: {image_file}")
            pixelate(image_file, output_file, pixel_size)
        else:
            print(f"DEBUG: Skipping non-image file: {image_file}")

if __name__ == "__main__":
    print("DEBUG: Starting pixelation script...")
    if len(sys.argv) < 3:
        print("Usage: PixelateImages.py <input_directory> <output_directory>")
        sys.exit(1)

    input_directory = sys.argv[1]
    output_directory = sys.argv[2]
    process_images(input_directory, output_directory)
    print("DEBUG: Pixelation completed.")
