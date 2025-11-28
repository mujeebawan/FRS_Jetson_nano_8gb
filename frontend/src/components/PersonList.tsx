import { useEffect, useState } from 'react';
import { personsApi } from '../services/api';
import { Trash2, UserPlus, Image } from 'lucide-react';

interface Person {
  id: number;
  name: string;
  embedding_count: number;
}

export function PersonList() {
  const [persons, setPersons] = useState<Person[]>([]);
  const [loading, setLoading] = useState(true);
  const [enrollName, setEnrollName] = useState('');
  const [enrollFile, setEnrollFile] = useState<File | null>(null);
  const [enrolling, setEnrolling] = useState(false);

  useEffect(() => {
    loadPersons();
  }, []);

  const loadPersons = async () => {
    try {
      setLoading(true);
      const response = await personsApi.list();
      setPersons(response.data);
    } catch (err) {
      console.error('Failed to load persons:', err);
    } finally {
      setLoading(false);
    }
  };

  const handleEnroll = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!enrollName || !enrollFile) return;

    try {
      setEnrolling(true);
      await personsApi.enroll(enrollName, enrollFile);
      setEnrollName('');
      setEnrollFile(null);
      loadPersons();
    } catch (err) {
      console.error('Enrollment failed:', err);
      alert('Enrollment failed. Make sure the image contains a clear face.');
    } finally {
      setEnrolling(false);
    }
  };

  const handleDelete = async (personId: number) => {
    if (!confirm('Are you sure you want to delete this person?')) return;

    try {
      await personsApi.delete(personId);
      loadPersons();
    } catch (err) {
      console.error('Delete failed:', err);
    }
  };

  const handleAddImage = async (personId: number, file: File) => {
    try {
      await personsApi.addImage(personId, file);
      loadPersons();
    } catch (err) {
      console.error('Add image failed:', err);
      alert('Failed to add image. Make sure it contains a clear face.');
    }
  };

  return (
    <div className="person-list">
      <h3>Enrolled Persons</h3>

      {/* Enrollment Form */}
      <form onSubmit={handleEnroll} className="enroll-form">
        <input
          type="text"
          placeholder="Person Name"
          value={enrollName}
          onChange={(e) => setEnrollName(e.target.value)}
          required
        />
        <input
          type="file"
          accept="image/*"
          onChange={(e) => setEnrollFile(e.target.files?.[0] || null)}
          required
        />
        <button type="submit" disabled={enrolling || !enrollName || !enrollFile}>
          <UserPlus size={16} />
          {enrolling ? 'Enrolling...' : 'Enroll'}
        </button>
      </form>

      {/* Person List */}
      {loading ? (
        <div className="loading">Loading...</div>
      ) : persons.length === 0 ? (
        <div className="empty">No persons enrolled yet</div>
      ) : (
        <ul className="persons">
          {persons.map((person) => (
            <li key={person.id} className="person-item">
              <div className="person-info">
                <span className="person-name">{person.name}</span>
                <span className="embedding-count">{person.embedding_count} image(s)</span>
              </div>
              <div className="person-actions">
                <label className="add-image-btn" title="Add more images">
                  <Image size={16} />
                  <input
                    type="file"
                    accept="image/*"
                    hidden
                    onChange={(e) => {
                      if (e.target.files?.[0]) {
                        handleAddImage(person.id, e.target.files[0]);
                      }
                    }}
                  />
                </label>
                <button
                  onClick={() => handleDelete(person.id)}
                  className="delete-btn"
                  title="Delete"
                >
                  <Trash2 size={16} />
                </button>
              </div>
            </li>
          ))}
        </ul>
      )}
    </div>
  );
}

export default PersonList;
