import replicate
from concurrent.futures import ThreadPoolExecutor, as_completed
from typing import List, Union, Literal, TypedDict, Optional
from enum import Enum
import logging
from tqdm import tqdm
from pathlib import Path
from PIL import Image
import io
import os
from tenacity import retry, stop_after_attempt, wait_fixed

class ModalityType(str, Enum):
    TEXT = "text"
    IMAGE = "vision"

class EmbeddingInput(TypedDict):
    input_data: Union[str, Path, io.BytesIO]
    modality: ModalityType

def resize_image_if_needed(image_path: Union[str, Path], max_size_kb: int = 256) -> io.BytesIO:
    """
    Resize image if it's larger than max_size_kb.
    Returns BytesIO object containing the (potentially resized) image.
    """
    max_size_bytes = max_size_kb * 1024
    
    # Check original file size
    file_size = os.path.getsize(image_path)
    
    # Open the image
    with Image.open(image_path) as img:
        # Convert to RGB if necessary (handles PNG with transparency)
        if img.mode in ('RGBA', 'P'):
            img = img.convert('RGB')
        
        # If file is already small enough, just return it
        if file_size <= max_size_bytes:
            img_byte_arr = io.BytesIO()
            img.save(img_byte_arr, format='JPEG', quality=95)
            img_byte_arr.seek(0)
            return img_byte_arr
        
        # Calculate scaling factor
        scale = (max_size_bytes / file_size) ** 0.5
        
        # Start with 90% quality
        quality = 90
        
        while True:
            # Resize image
            new_width = int(img.width * scale)
            new_height = int(img.height * scale)
            resized_img = img.resize((new_width, new_height), Image.Resampling.LANCZOS)
            
            # Save to BytesIO
            img_byte_arr = io.BytesIO()
            resized_img.save(img_byte_arr, format='JPEG', quality=quality)
            
            # Check new size
            new_size = img_byte_arr.tell()
            
            if new_size <= max_size_bytes:
                img_byte_arr.seek(0)
                return img_byte_arr
            
            # If still too large, reduce quality or scale
            if quality > 30:
                quality -= 10
            else:
                scale *= 0.9

def get_single_embedding(input_data: Union[str, Path, io.BytesIO], modality: ModalityType) -> Optional[List[float]]:
    """Get embeddings for a single input (text or image)."""
    try:
        if modality == ModalityType.TEXT:
            input_dict = {
                "text_input": input_data,
                "modality": "text"
            }
        else:  # IMAGE
            if isinstance(input_data, (str, Path)):
                # Resize image if needed
                img_data = resize_image_if_needed(input_data)
                input_dict = {
                    "input": img_data,
                    "modality": "vision"
                }
            else:  # Already a BytesIO object
                input_dict = {
                    "input": input_data,
                    "modality": "vision"
                }
        
        output = replicate.run(
            "daanelson/imagebind:0383f62e173dc821ec52663ed22a076d9c970549c209666ac3db181618b7a304",
            input=input_dict
        )
        return output
    except Exception as e:
        logging.error(f"Error processing input: {str(e)}")
        return None

def get_embeddings_batch(
    inputs: List[EmbeddingInput],
    max_workers: int = 4,
    show_progress: bool = True,
    retry_attempts: int = 2
) -> List[Optional[List[float]]]:
    """Base function to get embeddings for multiple inputs using parallel processing."""
    logging.basicConfig(level=logging.INFO)
    logger = logging.getLogger(__name__)
    results = {}
    
    # set a long wait time to get around rate limits
    @retry(stop=stop_after_attempt(retry_attempts), wait=wait_fixed(30))
    def process_input(args):
        idx, input_item = args
        try:
            embedding = get_single_embedding(
                input_data=input_item['input_data'],
                modality=input_item['modality']
            )
            if embedding is not None:
                return idx, embedding
            else:
                raise Exception("Failed to get embedding, retrying...")
        except Exception as e:
            logger.error(f"Error processing input {idx}: {str(e)}, retrying...")
            raise Exception(f"Error processing input {idx}: {str(e)}, retrying...")
    
    with ThreadPoolExecutor(max_workers=max_workers) as executor:
        future_to_idx = {
            executor.submit(process_input, (idx, input_item)): idx 
            for idx, input_item in enumerate(inputs)
        }
        
        futures = as_completed(future_to_idx)
        if show_progress:
            futures = tqdm(futures, total=len(inputs), desc="Processing inputs")
            
        for future in futures:
            try:
                idx, embedding = future.result()
                results[idx] = embedding
            except Exception as e:
                logger.error(f"Error processing future: {str(e)}")
                idx = future_to_idx[future]
                results[idx] = None
    
    return [results.get(i) for i in range(len(inputs))]

def batch_text_embeddings(
    texts: List[str],
    max_workers: int = 4,
    show_progress: bool = False,
    retry_attempts: int = 2
) -> List[Optional[List[float]]]:
    """
    High-level function to get embeddings for a list of texts.
    """
    inputs = [
        {"input_data": text, "modality": ModalityType.TEXT}
        for text in texts
    ]
    
    return get_embeddings_batch(
        inputs=inputs,
        max_workers=max_workers,
        show_progress=show_progress,
        retry_attempts=retry_attempts
    )

def batch_image_embeddings(
    image_paths: List[str],
    max_workers: int = 4,
    show_progress: bool = True,
    retry_attempts: int = 2,
    validate_paths: bool = True,
    max_size_kb: int = 256
) -> List[Optional[List[float]]]:
    """
    High-level function to get embeddings for a list of image paths.
    
    Args:
        image_paths: List of paths to image files
        max_workers: Maximum number of concurrent threads
        show_progress: Whether to show a progress bar
        retry_attempts: Number of retry attempts for failed requests
        validate_paths: Whether to validate image paths before processing
        max_size_kb: Maximum image size in KB before resizing
    """
    # Validate paths if requested
    if validate_paths:
        valid_paths = []
        for path in image_paths:
            try:
                if Path(path).is_file():
                    valid_paths.append(path)
                else:
                    logging.warning(f"Image path does not exist or is not a file: {path}")
                    valid_paths.append(None)
            except Exception as e:
                logging.error(f"Error validating path {path}: {str(e)}")
                valid_paths.append(None)
        
        # Filter out None values while keeping track of original indices
        valid_inputs = [
            {"input_data": path, "modality": ModalityType.IMAGE}
            for path in valid_paths
            if path is not None
        ]
        
        if not valid_inputs:
            logging.error("No valid image paths provided")
            return [None] * len(image_paths)
    else:
        valid_inputs = [
            {"input_data": path, "modality": ModalityType.IMAGE}
            for path in image_paths
        ]
    
    return get_embeddings_batch(
        inputs=valid_inputs,
        max_workers=max_workers,
        show_progress=show_progress,
        retry_attempts=retry_attempts
    )

# Example usage
if __name__ == "__main__":
    # Example with texts
    sample_texts = [
        "A beautiful sunset over the ocean",
        "A busy city street at night",
        "Mountains covered in snow"
    ]
    
    text_embeddings = batch_text_embeddings(
        texts=sample_texts,
        max_workers=4,
        show_progress=True
    )
    print(f"Processed {len([e for e in text_embeddings if e is not None])}/{len(sample_texts)} texts")
    
    # Example with images
    sample_image_paths = [
        "path/to/image1.jpg",
        "path/to/image2.jpg",
        "path/to/image3.jpg"
    ]
    
    image_embeddings = batch_image_embeddings(
        image_paths=sample_image_paths,
        max_workers=4,
        show_progress=True,
        validate_paths=True,
        max_size_kb=256  # Maximum image size in KB
    )
    print(f"Processed {len([e for e in image_embeddings if e is not None])}/{len(sample_image_paths)} images")
