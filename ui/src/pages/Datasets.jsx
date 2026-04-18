import { useState, useEffect } from 'react';
import { Plus } from 'lucide-react';
import FolderCard from '../components/FolderCard';
import Modal from '../components/Modal';
import { listDatasets, createDataset, deleteDataset, renameDataset } from '../api';

export default function Datasets({ navigate, setSelectedDataset }) {
  const [datasets, setDatasets] = useState([]);
  const [isCreateOpen, setIsCreateOpen] = useState(false);
  const [newDatasetName, setNewDatasetName] = useState('');
  const [datasetToDelete, setDatasetToDelete] = useState(null);
  
  const [datasetToRename, setDatasetToRename] = useState(null);
  const [renameDatasetName, setRenameDatasetName] = useState('');

  const fetchDatasets = async () => {
    try { setDatasets(await listDatasets()); } catch (err) {}
  };

  useEffect(() => {
    fetchDatasets();
  }, []);

  const handleCreate = async (e) => {
    e.preventDefault();
    if (!newDatasetName.trim()) return;
    try {
      const ds = await createDataset(newDatasetName.trim());
      setIsCreateOpen(false);
      setNewDatasetName('');
      fetchDatasets();
      setSelectedDataset(ds);
      navigate('dataset-detail');
    } catch (err) {
      alert(err.message);
    }
  };

  const handleDelete = async () => {
    if (!datasetToDelete) return;
    try {
      await deleteDataset(datasetToDelete.id);
      setDatasetToDelete(null);
      fetchDatasets();
    } catch (err) {
      alert(err.message);
    }
  };

  const handleRename = async (e) => {
    e.preventDefault();
    if (!renameDatasetName.trim() || !datasetToRename) return;
    try {
      await renameDataset(datasetToRename.id, renameDatasetName.trim());
      setDatasetToRename(null);
      setRenameDatasetName('');
      fetchDatasets();
    } catch (err) {
      alert(err.message);
    }
  };

  return (
    <div className="animate-fade-in">
      <div className="view-header">
        <h2>Datasets</h2>
        <p>Manage your raw dataset collections for jobs.</p>
      </div>

      <div style={{ marginBottom: '1.5rem' }}>
        <button className="btn" onClick={() => setIsCreateOpen(true)}>
          <Plus size={16} /> New Dataset
        </button>
      </div>

      <Modal isOpen={isCreateOpen} onClose={() => setIsCreateOpen(false)} title="Create New Dataset">
        <form onSubmit={handleCreate}>
          <label style={{ display: 'block', marginBottom: '0.5rem', color: 'var(--text-muted)' }}>Dataset Name</label>
          <input 
            type="text" autoFocus value={newDatasetName} onChange={e => setNewDatasetName(e.target.value)}
            placeholder="e.g., raw_faces"
            style={{ width: '100%', padding: '0.75rem', borderRadius: '4px', border: '1px solid var(--surface-border)', background: 'var(--bg-color)', color: 'var(--text-main)', marginBottom: '1.5rem', fontSize: '1rem' }} 
          />
          <div style={{ display: 'flex', gap: '0.5rem', justifyContent: 'flex-end' }}>
            <button type="button" className="btn btn-secondary" onClick={() => setIsCreateOpen(false)}>Cancel</button>
            <button type="submit" className="btn" disabled={!newDatasetName.trim()}>Create</button>
          </div>
        </form>
      </Modal>

      <Modal isOpen={!!datasetToDelete} onClose={() => setDatasetToDelete(null)} title="Delete Dataset">
        <p style={{ marginBottom: '1.5rem' }}>Are you sure you want to delete <strong>{datasetToDelete?.name}</strong>? This will permanently delete all raw images inside, and unassign it from any linked jobs.</p>
        <div style={{ display: 'flex', gap: '0.5rem', justifyContent: 'flex-end' }}>
          <button className="btn btn-secondary" onClick={() => setDatasetToDelete(null)}>Cancel</button>
          <button className="btn btn-danger" onClick={handleDelete}>Delete Permanently</button>
        </div>
      </Modal>

      <Modal isOpen={!!datasetToRename} onClose={() => setDatasetToRename(null)} title="Rename Dataset">
        <form onSubmit={handleRename}>
          <label style={{ display: 'block', marginBottom: '0.5rem', color: 'var(--text-muted)' }}>New Dataset Name</label>
          <input 
            type="text" autoFocus value={renameDatasetName} onChange={e => setRenameDatasetName(e.target.value)}
            style={{ width: '100%', padding: '0.75rem', borderRadius: '4px', border: '1px solid var(--surface-border)', background: 'var(--bg-color)', color: 'var(--text-main)', marginBottom: '1.5rem', fontSize: '1rem' }} 
          />
          <div style={{ display: 'flex', gap: '0.5rem', justifyContent: 'flex-end' }}>
            <button type="button" className="btn btn-secondary" onClick={() => setDatasetToRename(null)}>Cancel</button>
            <button type="submit" className="btn" disabled={!renameDatasetName.trim()}>Rename</button>
          </div>
        </form>
      </Modal>

      {datasets.length === 0 ? (
        <div className="glass-panel" style={{ padding: '3rem', textAlign: 'center', color: 'var(--text-muted)' }}>
          No datasets yet. Create one to get started.
        </div>
      ) : (
        <div style={{ display: 'flex', flexDirection: 'column', gap: '0.75rem' }}>
          {datasets.map(ds => (
            <FolderCard
              key={ds.id}
              icon="cluster"
              title={ds.name}
              subtitle={`${ds.image_count || 0} images · Created ${new Date(ds.created_at).toLocaleDateString()}`}
              onClick={() => { setSelectedDataset(ds); navigate('dataset-detail'); }}
              onRename={() => { setDatasetToRename(ds); setRenameDatasetName(ds.name); }}
              onDelete={() => setDatasetToDelete(ds)}
            />
          ))}
        </div>
      )}
    </div>
  );
}
