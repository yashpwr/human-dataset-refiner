import { useState, useEffect, useRef } from 'react';
import { ArrowLeft, UploadCloud } from 'lucide-react';
import ImageGrid from '../components/ImageGrid';
import Modal from '../components/Modal';
import { listDatasetImages, uploadToDataset, deleteDatasetImage, dataUrl } from '../api';

export default function DatasetDetail({ dataset, navigate }) {
  const [images, setImages] = useState([]);
  const [imageToDelete, setImageToDelete] = useState(null);
  const fileInputRef = useRef(null);

  const fetchImages = async () => {
    try {
      const data = await listDatasetImages(dataset.id);
      setImages(data.images || []);
    } catch (err) {}
  };

  useEffect(() => {
    fetchImages();
  }, [dataset.id]);

  const handleUpload = async (files) => {
    if (!files?.length) return;
    try {
      await uploadToDataset(dataset.id, Array.from(files));
      fetchImages();
    } catch (err) {
      alert(err.message);
    }
  };

  const handleDeleteImage = async () => {
    if (!imageToDelete) return;
    try {
      await deleteDatasetImage(dataset.id, imageToDelete);
      setImages(prev => prev.filter(i => i !== imageToDelete));
      setImageToDelete(null);
    } catch (err) { alert(err.message); }
  };

  return (
    <div className="animate-fade-in">
      <button className="btn btn-secondary" onClick={() => navigate('datasets')} style={{ marginBottom: '1.5rem' }}>
        <ArrowLeft size={16} /> All Datasets
      </button>
      <div className="view-header">
        <h2>{dataset.name}</h2>
        <p>{images.length} images in this dataset</p>
      </div>

      <div className="upload-zone" style={{ marginBottom: '2rem' }}
        onClick={() => fileInputRef.current?.click()}
        onDragOver={e => e.preventDefault()}
        onDrop={e => { e.preventDefault(); handleUpload(e.dataTransfer.files); }}>
        <input type="file" ref={fileInputRef} style={{ display: 'none' }} accept="image/*,.zip" multiple
          onChange={e => handleUpload(e.target.files)} />
        <UploadCloud size={32} style={{ marginBottom: '1rem', color: 'var(--text-muted)' }} />
        <h4>Upload Images</h4>
        <p style={{ fontSize: '0.85rem', marginTop: '0.5rem' }}>Drag images or a zip file here</p>
      </div>

      {images.length === 0 ? (
        <div style={{ textAlign: 'center', padding: '3rem', color: 'var(--text-muted)' }}>
          No images yet. Upload files to begin.
        </div>
      ) : (
        <ImageGrid
          images={images}
          getUrl={(fn) => dataUrl(`datasets/${dataset.name}/${fn}`)}
          onDelete={setImageToDelete}
        />
      )}

      <Modal isOpen={!!imageToDelete} onClose={() => setImageToDelete(null)} title="Delete Image">
        <p style={{ marginBottom: '1.5rem' }}>Are you sure you want to delete <strong>{imageToDelete}</strong> from this dataset?</p>
        <div style={{ display: 'flex', gap: '0.5rem', justifyContent: 'flex-end' }}>
          <button className="btn btn-secondary" onClick={() => setImageToDelete(null)}>Cancel</button>
          <button className="btn btn-danger" onClick={handleDeleteImage}>Delete Image</button>
        </div>
      </Modal>
    </div>
  );
}
