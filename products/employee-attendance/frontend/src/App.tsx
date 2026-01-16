import { useState, useEffect, useCallback } from 'react';
import {
  Users, Clock, UserCheck, UserX, AlertTriangle, Calendar,
  Settings, Camera, BarChart3, LogOut, Menu, X, Building2,
  TrendingUp, Coffee, ChevronRight, Search, Plus, Download,
  Eye, Edit, Trash2, RefreshCw, Video, Play, Pause, Maximize2
} from 'lucide-react';
import { AuthProvider, useAuth } from './contexts/AuthContext';
import { Card, CardContent, CardHeader, CardTitle } from './components/ui/card';
import { Button } from './components/ui/button';
import { Badge } from './components/ui/badge';
import { Input } from './components/ui/input';
import { cn } from './lib/utils';

// API base URL
const API_BASE_URL = import.meta.env.VITE_API_URL || 'http://localhost:8001/api';

interface DashboardStats {
  today: {
    total_employees: number;
    present: number;
    late: number;
    absent: number;
    checked_out: number;
    attendance_rate: number;
  };
  departments: Array<{
    name: string;
    code: string;
    total: number;
    present: number;
  }>;
}

interface Employee {
  id: number;
  employee_id: string;
  name: string;
  email: string | null;
  department_id: number | null;
  department_name: string | null;
  position: string | null;
  shift_start: string;
  shift_end: string;
  is_active: boolean;
  has_face: boolean;
}

interface PresentEmployee {
  id: number;
  employee_id: string;
  name: string;
  department: string | null;
  position: string | null;
  check_in: string | null;
  check_out: string | null;
  status: string;
  work_hours: number | null;
}

interface Activity {
  type: 'check_in' | 'check_out';
  employee_id: string;
  name: string;
  department: string | null;
  time: string;
  status?: string;
  late_minutes?: number;
}

interface Department {
  id: number;
  name: string;
  code: string;
  employee_count: number;
}

// Utility function for API calls
async function apiFetch(endpoint: string, token: string, options?: RequestInit) {
  const response = await fetch(`${API_BASE_URL}${endpoint}`, {
    ...options,
    headers: {
      'Authorization': `Bearer ${token}`,
      ...(options?.headers || {}),
    },
  });
  if (!response.ok) throw new Error(`API Error: ${response.status}`);
  return response.json();
}

function LoginPage() {
  const [username, setUsername] = useState('');
  const [password, setPassword] = useState('');
  const [error, setError] = useState('');
  const [loading, setLoading] = useState(false);
  const { login } = useAuth();

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setError('');
    setLoading(true);
    try {
      await login(username, password);
    } catch {
      setError('Invalid credentials');
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="min-h-screen bg-gradient-to-br from-blue-50 to-indigo-100 flex items-center justify-center p-4">
      <Card className="w-full max-w-md shadow-xl">
        <CardHeader className="text-center pb-2">
          <div className="mx-auto w-16 h-16 bg-blue-600 rounded-2xl flex items-center justify-center mb-4">
            <Clock className="w-8 h-8 text-white" />
          </div>
          <CardTitle className="text-2xl font-bold text-gray-900">Employee Attendance</CardTitle>
          <p className="text-gray-500 mt-1">Sign in to your account</p>
        </CardHeader>
        <CardContent>
          <form onSubmit={handleSubmit} className="space-y-4">
            {error && (
              <div className="bg-red-50 text-red-600 px-4 py-2 rounded-lg text-sm">{error}</div>
            )}
            <div>
              <label className="block text-sm font-medium text-gray-700 mb-1">Username</label>
              <Input
                type="text"
                value={username}
                onChange={(e) => setUsername(e.target.value)}
                placeholder="Enter username"
                required
              />
            </div>
            <div>
              <label className="block text-sm font-medium text-gray-700 mb-1">Password</label>
              <Input
                type="password"
                value={password}
                onChange={(e) => setPassword(e.target.value)}
                placeholder="Enter password"
                required
              />
            </div>
            <Button type="submit" className="w-full" disabled={loading}>
              {loading ? 'Signing in...' : 'Sign In'}
            </Button>
          </form>
          <p className="text-xs text-center text-gray-400 mt-4">Default: admin / admin123</p>
        </CardContent>
      </Card>
    </div>
  );
}

// Dashboard Tab
function DashboardTab({ token }: { token: string }) {
  const [stats, setStats] = useState<DashboardStats | null>(null);
  const [presentEmployees, setPresentEmployees] = useState<PresentEmployee[]>([]);
  const [activities, setActivities] = useState<Activity[]>([]);
  const [loading, setLoading] = useState(true);

  const fetchData = useCallback(async () => {
    try {
      const [statsData, presentData, activityData] = await Promise.all([
        apiFetch('/dashboard/stats', token),
        apiFetch('/dashboard/present', token),
        apiFetch('/dashboard/activity?limit=10', token),
      ]);
      setStats(statsData);
      setPresentEmployees(presentData.still_present?.employees || []);
      setActivities(activityData.activities || []);
    } catch (err) {
      console.error('Error fetching dashboard:', err);
    } finally {
      setLoading(false);
    }
  }, [token]);

  useEffect(() => {
    fetchData();
    const interval = setInterval(fetchData, 30000);
    return () => clearInterval(interval);
  }, [fetchData]);

  if (loading) {
    return (
      <div className="flex items-center justify-center py-12">
        <RefreshCw className="w-8 h-8 animate-spin text-blue-600" />
      </div>
    );
  }

  return (
    <div className="space-y-6">
      {/* Stats Cards */}
      <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-4">
        <Card className="bg-gradient-to-br from-blue-500 to-blue-600 text-white border-0">
          <CardContent className="p-5">
            <div className="flex items-center justify-between">
              <div>
                <p className="text-blue-100 text-sm font-medium">Total Employees</p>
                <p className="text-3xl font-bold mt-1">{stats?.today.total_employees || 0}</p>
              </div>
              <div className="w-12 h-12 bg-white/20 rounded-xl flex items-center justify-center">
                <Users className="w-6 h-6" />
              </div>
            </div>
          </CardContent>
        </Card>

        <Card className="bg-gradient-to-br from-green-500 to-green-600 text-white border-0">
          <CardContent className="p-5">
            <div className="flex items-center justify-between">
              <div>
                <p className="text-green-100 text-sm font-medium">Present Today</p>
                <p className="text-3xl font-bold mt-1">{stats?.today.present || 0}</p>
                <p className="text-green-100 text-xs mt-1">{stats?.today.attendance_rate || 0}% attendance</p>
              </div>
              <div className="w-12 h-12 bg-white/20 rounded-xl flex items-center justify-center">
                <UserCheck className="w-6 h-6" />
              </div>
            </div>
          </CardContent>
        </Card>

        <Card className="bg-gradient-to-br from-amber-500 to-amber-600 text-white border-0">
          <CardContent className="p-5">
            <div className="flex items-center justify-between">
              <div>
                <p className="text-amber-100 text-sm font-medium">Late Arrivals</p>
                <p className="text-3xl font-bold mt-1">{stats?.today.late || 0}</p>
              </div>
              <div className="w-12 h-12 bg-white/20 rounded-xl flex items-center justify-center">
                <AlertTriangle className="w-6 h-6" />
              </div>
            </div>
          </CardContent>
        </Card>

        <Card className="bg-gradient-to-br from-red-500 to-red-600 text-white border-0">
          <CardContent className="p-5">
            <div className="flex items-center justify-between">
              <div>
                <p className="text-red-100 text-sm font-medium">Absent</p>
                <p className="text-3xl font-bold mt-1">{stats?.today.absent || 0}</p>
              </div>
              <div className="w-12 h-12 bg-white/20 rounded-xl flex items-center justify-center">
                <UserX className="w-6 h-6" />
              </div>
            </div>
          </CardContent>
        </Card>
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
        {/* Present Employees */}
        <Card className="lg:col-span-2">
          <CardHeader className="flex flex-row items-center justify-between pb-2">
            <CardTitle className="text-base font-semibold">Who's In Today</CardTitle>
            <Badge variant="secondary">{presentEmployees.length} present</Badge>
          </CardHeader>
          <CardContent>
            {presentEmployees.length === 0 ? (
              <div className="text-center py-8 text-gray-500">
                <Coffee className="w-12 h-12 mx-auto mb-3 text-gray-300" />
                <p>No one has checked in yet</p>
              </div>
            ) : (
              <div className="grid grid-cols-2 md:grid-cols-3 gap-3">
                {presentEmployees.slice(0, 9).map((emp) => (
                  <div key={emp.id} className="flex items-center gap-3 p-3 bg-gray-50 rounded-lg">
                    <div className="w-10 h-10 bg-blue-100 rounded-full flex items-center justify-center flex-shrink-0">
                      <span className="text-sm font-semibold text-blue-600">{emp.name.charAt(0)}</span>
                    </div>
                    <div className="min-w-0">
                      <p className="text-sm font-medium text-gray-900 truncate">{emp.name}</p>
                      <p className="text-xs text-gray-500">{emp.check_in}</p>
                    </div>
                  </div>
                ))}
              </div>
            )}
            {presentEmployees.length > 9 && (
              <button className="w-full mt-4 py-2 text-sm text-blue-600 hover:text-blue-700 flex items-center justify-center gap-1">
                View all {presentEmployees.length} employees
                <ChevronRight className="w-4 h-4" />
              </button>
            )}
          </CardContent>
        </Card>

        {/* Recent Activity */}
        <Card>
          <CardHeader className="pb-2">
            <CardTitle className="text-base font-semibold">Recent Activity</CardTitle>
          </CardHeader>
          <CardContent>
            <div className="space-y-3">
              {activities.length === 0 ? (
                <p className="text-center text-gray-500 py-4">No activity yet</p>
              ) : (
                activities.slice(0, 8).map((activity, idx) => (
                  <div key={idx} className="flex items-center gap-3 py-2 border-b border-gray-100 last:border-0">
                    <div className={cn(
                      "w-8 h-8 rounded-full flex items-center justify-center flex-shrink-0",
                      activity.type === 'check_in' ? "bg-green-100" : "bg-blue-100"
                    )}>
                      {activity.type === 'check_in' ? (
                        <UserCheck className="w-4 h-4 text-green-600" />
                      ) : (
                        <LogOut className="w-4 h-4 text-blue-600" />
                      )}
                    </div>
                    <div className="min-w-0 flex-1">
                      <p className="text-sm font-medium text-gray-900 truncate">{activity.name}</p>
                      <p className="text-xs text-gray-500">
                        {activity.type === 'check_in' ? 'In' : 'Out'} at {activity.time}
                        {activity.late_minutes && activity.late_minutes > 0 && (
                          <span className="text-amber-600 ml-1">({activity.late_minutes}m late)</span>
                        )}
                      </p>
                    </div>
                  </div>
                ))
              )}
            </div>
          </CardContent>
        </Card>
      </div>

      {/* Department Stats */}
      {stats?.departments && stats.departments.length > 0 && (
        <Card>
          <CardHeader className="pb-2">
            <CardTitle className="text-base font-semibold">Department Overview</CardTitle>
          </CardHeader>
          <CardContent>
            <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
              {stats.departments.map((dept) => (
                <div key={dept.code} className="p-4 bg-gray-50 rounded-lg">
                  <div className="flex items-center justify-between mb-2">
                    <span className="text-sm font-medium text-gray-900">{dept.name}</span>
                    <Badge variant="secondary" className="text-xs">{dept.code}</Badge>
                  </div>
                  <div className="flex items-end justify-between">
                    <div>
                      <span className="text-2xl font-bold text-gray-900">{dept.present}</span>
                      <span className="text-gray-500 text-sm">/{dept.total}</span>
                    </div>
                    <div className="w-16 h-2 bg-gray-200 rounded-full overflow-hidden">
                      <div
                        className="h-full bg-green-500 rounded-full"
                        style={{ width: `${(dept.present / Math.max(1, dept.total)) * 100}%` }}
                      />
                    </div>
                  </div>
                </div>
              ))}
            </div>
          </CardContent>
        </Card>
      )}
    </div>
  );
}

// Employees Tab
function EmployeesTab({ token }: { token: string }) {
  const [employees, setEmployees] = useState<Employee[]>([]);
  const [departments, setDepartments] = useState<Department[]>([]);
  const [loading, setLoading] = useState(true);
  const [search, setSearch] = useState('');
  const [showAddModal, setShowAddModal] = useState(false);
  const [showViewModal, setShowViewModal] = useState(false);
  const [showEditModal, setShowEditModal] = useState(false);
  const [selectedEmployee, setSelectedEmployee] = useState<Employee | null>(null);
  const [employeeDetails, setEmployeeDetails] = useState<any>(null);
  const [saving, setSaving] = useState(false);
  const [formData, setFormData] = useState({
    employee_id: '',
    name: '',
    email: '',
    phone: '',
    department_id: '',
    position: '',
    shift_start: '09:00',
    shift_end: '18:00',
  });
  const [selectedImage, setSelectedImage] = useState<File | null>(null);
  const [imagePreview, setImagePreview] = useState<string | null>(null);

  const fetchEmployees = useCallback(async () => {
    try {
      const data = await apiFetch(`/employees?search=${search}`, token);
      setEmployees(data.employees || []);
    } catch (err) {
      console.error('Error:', err);
    } finally {
      setLoading(false);
    }
  }, [token, search]);

  useEffect(() => {
    fetchEmployees();
  }, [fetchEmployees]);

  useEffect(() => {
    async function fetchDepts() {
      try {
        const data = await apiFetch('/departments', token);
        setDepartments(data.departments || []);
      } catch (err) {
        console.error('Error:', err);
      }
    }
    fetchDepts();
  }, [token]);

  const handleImageChange = (e: React.ChangeEvent<HTMLInputElement>) => {
    const file = e.target.files?.[0];
    if (file) {
      setSelectedImage(file);
      const reader = new FileReader();
      reader.onloadend = () => setImagePreview(reader.result as string);
      reader.readAsDataURL(file);
    }
  };

  const handleAdd = async (e: React.FormEvent) => {
    e.preventDefault();
    setSaving(true);
    try {
      const form = new FormData();
      form.append('employee_id', formData.employee_id);
      form.append('name', formData.name);
      if (formData.email) form.append('email', formData.email);
      if (formData.phone) form.append('phone', formData.phone);
      if (formData.department_id) form.append('department_id', formData.department_id);
      if (formData.position) form.append('position', formData.position);
      form.append('shift_start', formData.shift_start);
      form.append('shift_end', formData.shift_end);
      if (selectedImage) form.append('image', selectedImage);

      const response = await fetch(`${API_BASE_URL}/employees`, {
        method: 'POST',
        headers: { 'Authorization': `Bearer ${token}` },
        body: form,
      });

      if (!response.ok) {
        const err = await response.json();
        alert(err.detail || 'Failed to add employee');
        return;
      }

      setShowAddModal(false);
      setFormData({ employee_id: '', name: '', email: '', phone: '', department_id: '', position: '', shift_start: '09:00', shift_end: '18:00' });
      setSelectedImage(null);
      setImagePreview(null);
      fetchEmployees();
    } catch (err) {
      console.error('Error:', err);
      alert('Failed to add employee');
    } finally {
      setSaving(false);
    }
  };

  const handleDelete = async (id: number, name: string) => {
    if (!confirm(`Delete employee "${name}"? This cannot be undone.`)) return;

    try {
      const response = await fetch(`${API_BASE_URL}/employees/${id}`, {
        method: 'DELETE',
        headers: { 'Authorization': `Bearer ${token}` },
      });

      if (!response.ok) {
        const err = await response.json();
        alert(err.detail || 'Failed to delete employee');
        return;
      }

      fetchEmployees();
    } catch (err) {
      console.error('Error:', err);
      alert('Failed to delete employee');
    }
  };

  const handleView = async (emp: Employee) => {
    setSelectedEmployee(emp);
    setShowViewModal(true);
    try {
      const data = await apiFetch(`/employees/${emp.id}`, token);
      setEmployeeDetails(data);
    } catch (err) {
      console.error('Error fetching employee details:', err);
    }
  };

  const handleEditClick = (emp: Employee) => {
    setSelectedEmployee(emp);
    setFormData({
      employee_id: emp.employee_id,
      name: emp.name,
      email: emp.email || '',
      phone: '',
      department_id: emp.department_id?.toString() || '',
      position: emp.position || '',
      shift_start: emp.shift_start || '09:00',
      shift_end: emp.shift_end || '18:00',
    });
    setSelectedImage(null);
    setImagePreview(null);
    setShowEditModal(true);
  };

  const handleEdit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!selectedEmployee) return;
    setSaving(true);
    try {
      const form = new FormData();
      form.append('name', formData.name);
      if (formData.email) form.append('email', formData.email);
      if (formData.phone) form.append('phone', formData.phone);
      if (formData.department_id) form.append('department_id', formData.department_id);
      if (formData.position) form.append('position', formData.position);
      form.append('shift_start', formData.shift_start);
      form.append('shift_end', formData.shift_end);
      if (selectedImage) form.append('image', selectedImage);

      const response = await fetch(`${API_BASE_URL}/employees/${selectedEmployee.id}`, {
        method: 'PUT',
        headers: { 'Authorization': `Bearer ${token}` },
        body: form,
      });

      if (!response.ok) {
        const err = await response.json();
        alert(err.detail || 'Failed to update employee');
        return;
      }

      setShowEditModal(false);
      setSelectedEmployee(null);
      setSelectedImage(null);
      setImagePreview(null);
      fetchEmployees();
    } catch (err) {
      console.error('Error:', err);
      alert('Failed to update employee');
    } finally {
      setSaving(false);
    }
  };

  return (
    <div className="space-y-4">
      {/* Add Employee Modal */}
      {showAddModal && (
        <div className="fixed inset-0 bg-black/50 flex items-center justify-center z-50">
          <div className="bg-white rounded-lg shadow-xl w-full max-w-md mx-4">
            <div className="flex items-center justify-between px-6 py-4 border-b">
              <h3 className="text-lg font-semibold">Add Employee</h3>
              <button onClick={() => { setShowAddModal(false); setSelectedImage(null); setImagePreview(null); }} className="text-gray-400 hover:text-gray-600">
                <X className="w-5 h-5" />
              </button>
            </div>
            <form onSubmit={handleAdd} className="p-6 space-y-4">
              <div className="grid grid-cols-2 gap-4">
                <div>
                  <label className="block text-sm font-medium text-gray-700 mb-1">Employee ID *</label>
                  <Input
                    required
                    placeholder="EMP001"
                    value={formData.employee_id}
                    onChange={(e) => setFormData({...formData, employee_id: e.target.value})}
                  />
                </div>
                <div>
                  <label className="block text-sm font-medium text-gray-700 mb-1">Name *</label>
                  <Input
                    required
                    placeholder="Full Name"
                    value={formData.name}
                    onChange={(e) => setFormData({...formData, name: e.target.value})}
                  />
                </div>
              </div>
              <div className="grid grid-cols-2 gap-4">
                <div>
                  <label className="block text-sm font-medium text-gray-700 mb-1">Email</label>
                  <Input
                    type="email"
                    placeholder="email@example.com"
                    value={formData.email}
                    onChange={(e) => setFormData({...formData, email: e.target.value})}
                  />
                </div>
                <div>
                  <label className="block text-sm font-medium text-gray-700 mb-1">Phone</label>
                  <Input
                    placeholder="+1234567890"
                    value={formData.phone}
                    onChange={(e) => setFormData({...formData, phone: e.target.value})}
                  />
                </div>
              </div>
              <div className="grid grid-cols-2 gap-4">
                <div>
                  <label className="block text-sm font-medium text-gray-700 mb-1">Department</label>
                  <select
                    className="w-full px-3 py-2 border border-gray-300 rounded-md focus:outline-none focus:ring-2 focus:ring-blue-500"
                    value={formData.department_id}
                    onChange={(e) => setFormData({...formData, department_id: e.target.value})}
                  >
                    <option value="">Select Department</option>
                    {departments.map((d) => (
                      <option key={d.id} value={d.id}>{d.name}</option>
                    ))}
                  </select>
                </div>
                <div>
                  <label className="block text-sm font-medium text-gray-700 mb-1">Position</label>
                  <Input
                    placeholder="Job Title"
                    value={formData.position}
                    onChange={(e) => setFormData({...formData, position: e.target.value})}
                  />
                </div>
              </div>
              <div className="grid grid-cols-2 gap-4">
                <div>
                  <label className="block text-sm font-medium text-gray-700 mb-1">Shift Start</label>
                  <Input
                    type="time"
                    value={formData.shift_start}
                    onChange={(e) => setFormData({...formData, shift_start: e.target.value})}
                  />
                </div>
                <div>
                  <label className="block text-sm font-medium text-gray-700 mb-1">Shift End</label>
                  <Input
                    type="time"
                    value={formData.shift_end}
                    onChange={(e) => setFormData({...formData, shift_end: e.target.value})}
                  />
                </div>
              </div>
              <div>
                <label className="block text-sm font-medium text-gray-700 mb-1">Face Photo (for recognition)</label>
                <div className="flex items-start gap-4">
                  <div className="flex-1">
                    <input
                      type="file"
                      accept="image/*"
                      onChange={handleImageChange}
                      className="w-full text-sm text-gray-500 file:mr-4 file:py-2 file:px-4 file:rounded-md file:border-0 file:text-sm file:font-medium file:bg-blue-50 file:text-blue-700 hover:file:bg-blue-100"
                    />
                    <p className="text-xs text-gray-400 mt-1">Upload a clear front-facing photo for face recognition</p>
                  </div>
                  {imagePreview && (
                    <div className="w-20 h-20 rounded-lg overflow-hidden border-2 border-blue-200">
                      <img src={imagePreview} alt="Preview" className="w-full h-full object-cover" />
                    </div>
                  )}
                </div>
              </div>
              <div className="flex justify-end gap-3 pt-4">
                <Button type="button" variant="outline" onClick={() => setShowAddModal(false)}>Cancel</Button>
                <Button type="submit" disabled={saving}>
                  {saving ? <RefreshCw className="w-4 h-4 mr-2 animate-spin" /> : <Plus className="w-4 h-4 mr-2" />}
                  Add Employee
                </Button>
              </div>
            </form>
          </div>
        </div>
      )}

      {/* View Employee Modal */}
      {showViewModal && selectedEmployee && (
        <div className="fixed inset-0 bg-black/50 flex items-center justify-center z-50">
          <div className="bg-white rounded-lg shadow-xl w-full max-w-lg mx-4">
            <div className="flex items-center justify-between px-6 py-4 border-b">
              <h3 className="text-lg font-semibold">Employee Details</h3>
              <button onClick={() => { setShowViewModal(false); setSelectedEmployee(null); setEmployeeDetails(null); }} className="text-gray-400 hover:text-gray-600">
                <X className="w-5 h-5" />
              </button>
            </div>
            <div className="p-6">
              <div className="flex items-start gap-6 mb-6">
                <div className="w-24 h-24 bg-blue-100 rounded-xl flex items-center justify-center flex-shrink-0 overflow-hidden">
                  {selectedEmployee.has_face ? (
                    <img
                      src={`${API_BASE_URL}/employees/${selectedEmployee.id}/image`}
                      alt={selectedEmployee.name}
                      className="w-full h-full object-cover"
                      onError={(e) => {
                        (e.target as HTMLImageElement).style.display = 'none';
                        (e.target as HTMLImageElement).parentElement!.innerHTML = `<span class="text-3xl font-bold text-blue-600">${selectedEmployee.name.charAt(0)}</span>`;
                      }}
                    />
                  ) : (
                    <span className="text-3xl font-bold text-blue-600">{selectedEmployee.name.charAt(0)}</span>
                  )}
                </div>
                <div className="flex-1">
                  <h4 className="text-xl font-bold text-gray-900">{selectedEmployee.name}</h4>
                  <p className="text-gray-500">{selectedEmployee.employee_id}</p>
                  <div className="flex items-center gap-2 mt-2">
                    <Badge variant={selectedEmployee.is_active ? 'default' : 'secondary'}>
                      {selectedEmployee.is_active ? 'Active' : 'Inactive'}
                    </Badge>
                    <Badge variant={selectedEmployee.has_face ? 'default' : 'secondary'}>
                      {selectedEmployee.has_face ? 'Face Enrolled' : 'No Face'}
                    </Badge>
                  </div>
                </div>
              </div>
              <div className="grid grid-cols-2 gap-4 text-sm">
                <div className="p-3 bg-gray-50 rounded-lg">
                  <p className="text-gray-500 mb-1">Email</p>
                  <p className="font-medium">{selectedEmployee.email || '-'}</p>
                </div>
                <div className="p-3 bg-gray-50 rounded-lg">
                  <p className="text-gray-500 mb-1">Department</p>
                  <p className="font-medium">{selectedEmployee.department_name || '-'}</p>
                </div>
                <div className="p-3 bg-gray-50 rounded-lg">
                  <p className="text-gray-500 mb-1">Position</p>
                  <p className="font-medium">{selectedEmployee.position || '-'}</p>
                </div>
                <div className="p-3 bg-gray-50 rounded-lg">
                  <p className="text-gray-500 mb-1">Shift</p>
                  <p className="font-medium">{selectedEmployee.shift_start} - {selectedEmployee.shift_end}</p>
                </div>
                {employeeDetails?.today_attendance && (
                  <>
                    <div className="p-3 bg-green-50 rounded-lg">
                      <p className="text-gray-500 mb-1">Today Check In</p>
                      <p className="font-medium text-green-600">{employeeDetails.today_attendance.check_in || '-'}</p>
                    </div>
                    <div className="p-3 bg-blue-50 rounded-lg">
                      <p className="text-gray-500 mb-1">Today Check Out</p>
                      <p className="font-medium text-blue-600">{employeeDetails.today_attendance.check_out || '-'}</p>
                    </div>
                  </>
                )}
              </div>
              <div className="flex justify-end gap-3 pt-6">
                <Button variant="outline" onClick={() => { setShowViewModal(false); handleEditClick(selectedEmployee); }}>
                  <Edit className="w-4 h-4 mr-2" />
                  Edit
                </Button>
                <Button onClick={() => { setShowViewModal(false); setSelectedEmployee(null); }}>
                  Close
                </Button>
              </div>
            </div>
          </div>
        </div>
      )}

      {/* Edit Employee Modal */}
      {showEditModal && selectedEmployee && (
        <div className="fixed inset-0 bg-black/50 flex items-center justify-center z-50">
          <div className="bg-white rounded-lg shadow-xl w-full max-w-md mx-4 max-h-[90vh] overflow-y-auto">
            <div className="flex items-center justify-between px-6 py-4 border-b sticky top-0 bg-white">
              <h3 className="text-lg font-semibold">Edit Employee</h3>
              <button onClick={() => { setShowEditModal(false); setSelectedEmployee(null); setSelectedImage(null); setImagePreview(null); }} className="text-gray-400 hover:text-gray-600">
                <X className="w-5 h-5" />
              </button>
            </div>
            <form onSubmit={handleEdit} className="p-6 space-y-4">
              <div className="grid grid-cols-2 gap-4">
                <div>
                  <label className="block text-sm font-medium text-gray-700 mb-1">Employee ID</label>
                  <Input value={formData.employee_id} disabled className="bg-gray-100" />
                </div>
                <div>
                  <label className="block text-sm font-medium text-gray-700 mb-1">Name *</label>
                  <Input
                    required
                    value={formData.name}
                    onChange={(e) => setFormData({...formData, name: e.target.value})}
                  />
                </div>
              </div>
              <div className="grid grid-cols-2 gap-4">
                <div>
                  <label className="block text-sm font-medium text-gray-700 mb-1">Email</label>
                  <Input
                    type="email"
                    value={formData.email}
                    onChange={(e) => setFormData({...formData, email: e.target.value})}
                  />
                </div>
                <div>
                  <label className="block text-sm font-medium text-gray-700 mb-1">Phone</label>
                  <Input
                    value={formData.phone}
                    onChange={(e) => setFormData({...formData, phone: e.target.value})}
                  />
                </div>
              </div>
              <div className="grid grid-cols-2 gap-4">
                <div>
                  <label className="block text-sm font-medium text-gray-700 mb-1">Department</label>
                  <select
                    className="w-full px-3 py-2 border border-gray-300 rounded-md focus:outline-none focus:ring-2 focus:ring-blue-500"
                    value={formData.department_id}
                    onChange={(e) => setFormData({...formData, department_id: e.target.value})}
                  >
                    <option value="">Select Department</option>
                    {departments.map((d) => (
                      <option key={d.id} value={d.id}>{d.name}</option>
                    ))}
                  </select>
                </div>
                <div>
                  <label className="block text-sm font-medium text-gray-700 mb-1">Position</label>
                  <Input
                    value={formData.position}
                    onChange={(e) => setFormData({...formData, position: e.target.value})}
                  />
                </div>
              </div>
              <div className="grid grid-cols-2 gap-4">
                <div>
                  <label className="block text-sm font-medium text-gray-700 mb-1">Shift Start</label>
                  <Input
                    type="time"
                    value={formData.shift_start}
                    onChange={(e) => setFormData({...formData, shift_start: e.target.value})}
                  />
                </div>
                <div>
                  <label className="block text-sm font-medium text-gray-700 mb-1">Shift End</label>
                  <Input
                    type="time"
                    value={formData.shift_end}
                    onChange={(e) => setFormData({...formData, shift_end: e.target.value})}
                  />
                </div>
              </div>
              <div>
                <label className="block text-sm font-medium text-gray-700 mb-1">Update Face Photo</label>
                <div className="flex items-start gap-4">
                  <div className="flex-1">
                    <input
                      type="file"
                      accept="image/*"
                      onChange={handleImageChange}
                      className="w-full text-sm text-gray-500 file:mr-4 file:py-2 file:px-4 file:rounded-md file:border-0 file:text-sm file:font-medium file:bg-blue-50 file:text-blue-700 hover:file:bg-blue-100"
                    />
                    <p className="text-xs text-gray-400 mt-1">Leave empty to keep existing photo</p>
                  </div>
                  {imagePreview && (
                    <div className="w-16 h-16 rounded-lg overflow-hidden border-2 border-blue-200">
                      <img src={imagePreview} alt="Preview" className="w-full h-full object-cover" />
                    </div>
                  )}
                </div>
              </div>
              <div className="flex justify-end gap-3 pt-4">
                <Button type="button" variant="outline" onClick={() => { setShowEditModal(false); setSelectedEmployee(null); }}>Cancel</Button>
                <Button type="submit" disabled={saving}>
                  {saving ? <RefreshCw className="w-4 h-4 mr-2 animate-spin" /> : <Edit className="w-4 h-4 mr-2" />}
                  Update Employee
                </Button>
              </div>
            </form>
          </div>
        </div>
      )}

      <div className="flex items-center justify-between">
        <div className="relative w-64">
          <Search className="absolute left-3 top-1/2 -translate-y-1/2 w-4 h-4 text-gray-400" />
          <Input
            placeholder="Search employees..."
            value={search}
            onChange={(e) => setSearch(e.target.value)}
            className="pl-10"
          />
        </div>
        <Button onClick={() => setShowAddModal(true)}>
          <Plus className="w-4 h-4 mr-2" />
          Add Employee
        </Button>
      </div>

      <Card>
        <CardContent className="p-0">
          {loading ? (
            <div className="flex items-center justify-center py-12">
              <RefreshCw className="w-6 h-6 animate-spin text-gray-400" />
            </div>
          ) : employees.length === 0 ? (
            <div className="text-center py-12 text-gray-500">
              <Users className="w-12 h-12 mx-auto mb-3 text-gray-300" />
              <p>No employees found</p>
              <Button className="mt-4" onClick={() => setShowAddModal(true)}>
                <Plus className="w-4 h-4 mr-2" />
                Add First Employee
              </Button>
            </div>
          ) : (
            <div className="overflow-x-auto">
              <table className="w-full">
                <thead className="bg-gray-100 border-b border-gray-200">
                  <tr>
                    <th className="text-left px-4 py-3 text-xs font-semibold text-gray-700 uppercase tracking-wider">Employee</th>
                    <th className="text-left px-4 py-3 text-xs font-semibold text-gray-700 uppercase tracking-wider">ID</th>
                    <th className="text-left px-4 py-3 text-xs font-semibold text-gray-700 uppercase tracking-wider">Department</th>
                    <th className="text-left px-4 py-3 text-xs font-semibold text-gray-700 uppercase tracking-wider">Position</th>
                    <th className="text-left px-4 py-3 text-xs font-semibold text-gray-700 uppercase tracking-wider">Shift</th>
                    <th className="text-left px-4 py-3 text-xs font-semibold text-gray-700 uppercase tracking-wider">Status</th>
                    <th className="text-right px-4 py-3 text-xs font-semibold text-gray-700 uppercase tracking-wider">Actions</th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-gray-200">
                  {employees.map((emp) => (
                    <tr key={emp.id} className="hover:bg-blue-50/50">
                      <td className="px-4 py-3">
                        <div className="flex items-center gap-3">
                          <div className="relative">
                            <div className="w-10 h-10 bg-blue-600 rounded-full flex items-center justify-center">
                              <span className="text-sm font-bold text-white">{emp.name.charAt(0)}</span>
                            </div>
                            <div className={cn(
                              "absolute -bottom-0.5 -right-0.5 w-4 h-4 rounded-full flex items-center justify-center text-[10px] font-bold border-2 border-white",
                              emp.has_face ? "bg-green-500 text-white" : "bg-orange-500 text-white"
                            )} title={emp.has_face ? "Face enrolled" : "No face enrolled"}>
                              {emp.has_face ? "✓" : "!"}
                            </div>
                          </div>
                          <div>
                            <p className="font-semibold text-gray-900">{emp.name}</p>
                            <p className="text-sm text-gray-600">{emp.email || '-'}</p>
                          </div>
                        </div>
                      </td>
                      <td className="px-4 py-3 text-sm font-medium text-gray-800">{emp.employee_id}</td>
                      <td className="px-4 py-3 text-sm text-gray-800">{emp.department_name || '-'}</td>
                      <td className="px-4 py-3 text-sm text-gray-800">{emp.position || '-'}</td>
                      <td className="px-4 py-3 text-sm font-medium text-gray-800">{emp.shift_start} - {emp.shift_end}</td>
                      <td className="px-4 py-3">
                        <Badge variant={emp.is_active ? 'default' : 'secondary'} className={emp.is_active ? "bg-green-600 text-white" : ""}>
                          {emp.is_active ? 'Active' : 'Inactive'}
                        </Badge>
                      </td>
                      <td className="px-4 py-3 text-right">
                        <div className="flex items-center justify-end gap-1">
                          <Button variant="ghost" size="sm" onClick={() => handleView(emp)} className="text-blue-600 hover:text-blue-800 hover:bg-blue-100" title="View">
                            <Eye className="w-4 h-4" />
                          </Button>
                          <Button variant="ghost" size="sm" onClick={() => handleEditClick(emp)} className="text-green-600 hover:text-green-800 hover:bg-green-100" title="Edit">
                            <Edit className="w-4 h-4" />
                          </Button>
                          <Button variant="ghost" size="sm" onClick={() => handleDelete(emp.id, emp.name)} className="text-red-600 hover:text-red-800 hover:bg-red-100" title="Delete">
                            <Trash2 className="w-4 h-4" />
                          </Button>
                        </div>
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}
        </CardContent>
      </Card>
    </div>
  );
}

// Attendance Tab
function AttendanceTab({ token }: { token: string }) {
  const [attendance, setAttendance] = useState<any[]>([]);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    async function fetch() {
      try {
        const data = await apiFetch('/attendance/today', token);
        setAttendance(data.attendance || []);
      } catch (err) {
        console.error('Error:', err);
      } finally {
        setLoading(false);
      }
    }
    fetch();
  }, [token]);

  const getStatusColor = (status: string) => {
    switch (status) {
      case 'present': return 'bg-green-100 text-green-800';
      case 'late': return 'bg-amber-100 text-amber-800';
      case 'absent': return 'bg-red-100 text-red-800';
      default: return 'bg-gray-100 text-gray-800';
    }
  };

  return (
    <div className="space-y-4">
      <div className="flex items-center justify-between">
        <h3 className="text-lg font-semibold">Today's Attendance</h3>
        <Button variant="outline">
          <Download className="w-4 h-4 mr-2" />
          Export
        </Button>
      </div>

      <Card>
        <CardContent className="p-0">
          {loading ? (
            <div className="flex items-center justify-center py-12">
              <RefreshCw className="w-6 h-6 animate-spin text-gray-400" />
            </div>
          ) : (
            <div className="overflow-x-auto">
              <table className="w-full">
                <thead className="bg-gray-50 border-b">
                  <tr>
                    <th className="text-left px-4 py-3 text-xs font-medium text-gray-500 uppercase">Employee</th>
                    <th className="text-left px-4 py-3 text-xs font-medium text-gray-500 uppercase">Department</th>
                    <th className="text-left px-4 py-3 text-xs font-medium text-gray-500 uppercase">Check In</th>
                    <th className="text-left px-4 py-3 text-xs font-medium text-gray-500 uppercase">Check Out</th>
                    <th className="text-left px-4 py-3 text-xs font-medium text-gray-500 uppercase">Work Hours</th>
                    <th className="text-left px-4 py-3 text-xs font-medium text-gray-500 uppercase">Status</th>
                  </tr>
                </thead>
                <tbody className="divide-y">
                  {attendance.map((att, idx) => (
                    <tr key={idx} className="hover:bg-gray-50">
                      <td className="px-4 py-3">
                        <div className="flex items-center gap-3">
                          <div className="w-9 h-9 bg-blue-100 rounded-full flex items-center justify-center">
                            <span className="text-sm font-semibold text-blue-600">{att.name.charAt(0)}</span>
                          </div>
                          <div>
                            <p className="font-medium text-gray-900">{att.name}</p>
                            <p className="text-xs text-gray-500">{att.employee_id}</p>
                          </div>
                        </div>
                      </td>
                      <td className="px-4 py-3 text-sm text-gray-600">{att.department || '-'}</td>
                      <td className="px-4 py-3 text-sm text-gray-600">{att.check_in || '-'}</td>
                      <td className="px-4 py-3 text-sm text-gray-600">{att.check_out || '-'}</td>
                      <td className="px-4 py-3 text-sm text-gray-600">
                        {att.work_hours ? `${att.work_hours}h` : '-'}
                      </td>
                      <td className="px-4 py-3">
                        <span className={cn("px-2 py-1 rounded-full text-xs font-medium capitalize", getStatusColor(att.status))}>
                          {att.status}
                          {att.late_minutes && att.late_minutes > 0 && ` (${att.late_minutes}m)`}
                        </span>
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}
        </CardContent>
      </Card>
    </div>
  );
}

// Reports Tab
function ReportsTab({ token }: { token: string }) {
  const [startDate, setStartDate] = useState(() => {
    const d = new Date();
    d.setDate(d.getDate() - 7);
    return d.toISOString().split('T')[0];
  });
  const [endDate, setEndDate] = useState(() => new Date().toISOString().split('T')[0]);
  const [report, setReport] = useState<any[]>([]);
  const [loading, setLoading] = useState(false);
  const [summary, setSummary] = useState<any>(null);

  const fetchReport = useCallback(async () => {
    setLoading(true);
    try {
      const data = await apiFetch(`/attendance/report?start_date=${startDate}&end_date=${endDate}`, token);
      setReport(data.report || []);
      setSummary({
        total: data.total_employees,
        period: data.period
      });
    } catch (err) {
      console.error('Error:', err);
    } finally {
      setLoading(false);
    }
  }, [token, startDate, endDate]);

  useEffect(() => { fetchReport(); }, [fetchReport]);

  const downloadCSV = () => {
    window.open(`${API_BASE_URL}/attendance/report?start_date=${startDate}&end_date=${endDate}&format=csv`, '_blank');
  };

  return (
    <div className="space-y-4">
      <Card>
        <CardContent className="p-4">
          <div className="flex flex-wrap items-end gap-4">
            <div>
              <label className="block text-sm font-medium text-gray-700 mb-1">Start Date</label>
              <Input type="date" value={startDate} onChange={(e) => setStartDate(e.target.value)} />
            </div>
            <div>
              <label className="block text-sm font-medium text-gray-700 mb-1">End Date</label>
              <Input type="date" value={endDate} onChange={(e) => setEndDate(e.target.value)} />
            </div>
            <Button onClick={fetchReport} disabled={loading}>
              <RefreshCw className={cn("w-4 h-4 mr-2", loading && "animate-spin")} />
              Generate
            </Button>
            <Button variant="outline" onClick={downloadCSV}>
              <Download className="w-4 h-4 mr-2" />
              Export CSV
            </Button>
          </div>
        </CardContent>
      </Card>

      {summary && (
        <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
          <Card>
            <CardContent className="p-4 text-center">
              <p className="text-sm text-gray-500">Total Employees</p>
              <p className="text-2xl font-bold text-gray-900">{summary.total}</p>
            </CardContent>
          </Card>
          <Card>
            <CardContent className="p-4 text-center">
              <p className="text-sm text-gray-500">Report Period</p>
              <p className="text-sm font-medium text-gray-900">{summary.period?.start} to {summary.period?.end}</p>
            </CardContent>
          </Card>
          <Card>
            <CardContent className="p-4 text-center">
              <p className="text-sm text-gray-500">Records</p>
              <p className="text-2xl font-bold text-gray-900">{report.length}</p>
            </CardContent>
          </Card>
        </div>
      )}

      <Card>
        <CardContent className="p-0">
          {loading ? (
            <div className="flex items-center justify-center py-12">
              <RefreshCw className="w-6 h-6 animate-spin text-gray-400" />
            </div>
          ) : (
            <div className="overflow-x-auto">
              <table className="w-full">
                <thead className="bg-gray-50 border-b">
                  <tr>
                    <th className="text-left px-4 py-3 text-xs font-medium text-gray-500 uppercase">Employee</th>
                    <th className="text-left px-4 py-3 text-xs font-medium text-gray-500 uppercase">Department</th>
                    <th className="text-center px-4 py-3 text-xs font-medium text-gray-500 uppercase">Present</th>
                    <th className="text-center px-4 py-3 text-xs font-medium text-gray-500 uppercase">Late</th>
                    <th className="text-center px-4 py-3 text-xs font-medium text-gray-500 uppercase">Absent</th>
                    <th className="text-center px-4 py-3 text-xs font-medium text-gray-500 uppercase">Work Hours</th>
                    <th className="text-center px-4 py-3 text-xs font-medium text-gray-500 uppercase">Overtime</th>
                    <th className="text-center px-4 py-3 text-xs font-medium text-gray-500 uppercase">Rate</th>
                  </tr>
                </thead>
                <tbody className="divide-y">
                  {report.map((row, idx) => (
                    <tr key={idx} className="hover:bg-gray-50">
                      <td className="px-4 py-3">
                        <p className="font-medium text-gray-900">{row.name}</p>
                        <p className="text-xs text-gray-500">{row.employee_id}</p>
                      </td>
                      <td className="px-4 py-3 text-sm text-gray-600">{row.department}</td>
                      <td className="px-4 py-3 text-center text-sm font-medium text-green-600">{row.present_days}</td>
                      <td className="px-4 py-3 text-center text-sm font-medium text-amber-600">{row.late_days}</td>
                      <td className="px-4 py-3 text-center text-sm font-medium text-red-600">{row.absent_days}</td>
                      <td className="px-4 py-3 text-center text-sm text-gray-600">{row.total_work_hours}h</td>
                      <td className="px-4 py-3 text-center text-sm text-blue-600">{row.total_overtime_hours}h</td>
                      <td className="px-4 py-3 text-center">
                        <span className={cn(
                          "px-2 py-1 rounded-full text-xs font-medium",
                          row.attendance_percentage >= 90 ? "bg-green-100 text-green-800" :
                          row.attendance_percentage >= 70 ? "bg-amber-100 text-amber-800" :
                          "bg-red-100 text-red-800"
                        )}>
                          {row.attendance_percentage}%
                        </span>
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}
        </CardContent>
      </Card>
    </div>
  );
}

// Departments Tab
function DepartmentsTab({ token }: { token: string }) {
  const [departments, setDepartments] = useState<Department[]>([]);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    async function fetch() {
      try {
        const data = await apiFetch('/departments', token);
        setDepartments(data.departments || []);
      } catch (err) {
        console.error('Error:', err);
      } finally {
        setLoading(false);
      }
    }
    fetch();
  }, [token]);

  return (
    <div className="space-y-4">
      <Card>
        <CardHeader>
          <CardTitle className="text-base">All Departments</CardTitle>
        </CardHeader>
        <CardContent>
          {loading ? (
            <div className="flex items-center justify-center py-8">
              <RefreshCw className="w-6 h-6 animate-spin text-gray-400" />
            </div>
          ) : departments.length === 0 ? (
            <p className="text-center text-gray-500 py-8">No departments found</p>
          ) : (
            <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
              {departments.map((dept) => (
                <div key={dept.id} className="p-4 border rounded-lg hover:border-blue-300 transition-colors">
                  <div className="flex items-start justify-between mb-3">
                    <div className="w-10 h-10 bg-blue-100 rounded-lg flex items-center justify-center">
                      <Building2 className="w-5 h-5 text-blue-600" />
                    </div>
                    <Badge variant="secondary">{dept.code}</Badge>
                  </div>
                  <h3 className="font-semibold text-gray-900 mb-1">{dept.name}</h3>
                  <p className="text-sm text-gray-500">{dept.employee_count} employees</p>
                </div>
              ))}
            </div>
          )}
        </CardContent>
      </Card>
    </div>
  );
}

// Cameras Tab
function CamerasTab({ token }: { token: string }) {
  const [cameras, setCameras] = useState<any[]>([]);
  const [streamStatus, setStreamStatus] = useState<any>(null);
  const [loading, setLoading] = useState(true);

  const fetchData = useCallback(async () => {
    try {
      const [camerasData, statusData] = await Promise.all([
        apiFetch('/cameras', token),
        apiFetch('/stream/status', token),
      ]);
      setCameras(camerasData.cameras || []);
      setStreamStatus(statusData);
    } catch (err) {
      console.error('Error:', err);
    } finally {
      setLoading(false);
    }
  }, [token]);

  useEffect(() => {
    fetchData();
    const interval = setInterval(fetchData, 5000);
    return () => clearInterval(interval);
  }, [fetchData]);

  return (
    <div className="space-y-4">
      {/* Stream Status */}
      <Card>
        <CardHeader>
          <CardTitle className="text-base flex items-center gap-2">
            <Camera className="w-5 h-5" />
            Stream Status
          </CardTitle>
        </CardHeader>
        <CardContent>
          <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
            <div className="text-center p-3 bg-gray-50 rounded-lg">
              <p className="text-sm text-gray-500">Status</p>
              <Badge variant={streamStatus?.running ? 'default' : 'secondary'}>
                {streamStatus?.running ? 'Running' : 'Stopped'}
              </Badge>
            </div>
            <div className="text-center p-3 bg-gray-50 rounded-lg">
              <p className="text-sm text-gray-500">FPS</p>
              <p className="text-xl font-bold">{streamStatus?.fps || 0}</p>
            </div>
            <div className="text-center p-3 bg-gray-50 rounded-lg">
              <p className="text-sm text-gray-500">Pipeline</p>
              <p className="text-sm font-medium">{streamStatus?.pipeline || 'N/A'}</p>
            </div>
            <div className="text-center p-3 bg-gray-50 rounded-lg">
              <p className="text-sm text-gray-500">Cameras</p>
              <p className="text-xl font-bold">{streamStatus?.num_cameras || 0}</p>
            </div>
          </div>
        </CardContent>
      </Card>

      {/* Camera List */}
      <Card>
        <CardHeader>
          <CardTitle className="text-base">Camera Configuration</CardTitle>
        </CardHeader>
        <CardContent>
          {loading ? (
            <div className="flex items-center justify-center py-8">
              <RefreshCw className="w-6 h-6 animate-spin text-gray-400" />
            </div>
          ) : (
            <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
              {cameras.map((cam) => (
                <div key={cam.id} className="p-4 border rounded-lg">
                  <div className="flex items-start justify-between mb-3">
                    <div className="flex items-center gap-3">
                      <div className={cn(
                        "w-10 h-10 rounded-lg flex items-center justify-center",
                        cam.is_online ? "bg-green-100" : "bg-gray-100"
                      )}>
                        <Camera className={cn("w-5 h-5", cam.is_online ? "text-green-600" : "text-gray-400")} />
                      </div>
                      <div>
                        <h3 className="font-semibold text-gray-900">{cam.name}</h3>
                        <p className="text-xs text-gray-500">{cam.location || 'No location'}</p>
                      </div>
                    </div>
                    <Badge variant={cam.is_online ? 'default' : 'secondary'}>
                      {cam.is_online ? 'Online' : 'Offline'}
                    </Badge>
                  </div>
                  <div className="grid grid-cols-2 gap-2 text-sm">
                    <div>
                      <span className="text-gray-500">IP:</span>
                      <span className="ml-1 font-mono">{cam.ip_address}</span>
                    </div>
                    <div>
                      <span className="text-gray-500">Quality:</span>
                      <span className="ml-1">{cam.stream_quality}</span>
                    </div>
                    <div>
                      <span className="text-gray-500">Detection:</span>
                      <Badge variant={cam.detection_enabled ? 'default' : 'secondary'} className="ml-1 text-xs">
                        {cam.detection_enabled ? 'On' : 'Off'}
                      </Badge>
                    </div>
                    {cam.current_fps && (
                      <div>
                        <span className="text-gray-500">FPS:</span>
                        <span className="ml-1">{cam.current_fps}</span>
                      </div>
                    )}
                  </div>
                </div>
              ))}
            </div>
          )}
        </CardContent>
      </Card>
    </div>
  );
}

// Settings Tab
function SettingsTab({ token }: { token: string }) {
  const [settings, setSettings] = useState<any>(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    async function fetch() {
      try {
        const data = await apiFetch('/system/settings', token);
        setSettings(data);
      } catch (err) {
        console.error('Error:', err);
      } finally {
        setLoading(false);
      }
    }
    fetch();
  }, [token]);

  if (loading) {
    return (
      <div className="flex items-center justify-center py-12">
        <RefreshCw className="w-6 h-6 animate-spin text-gray-400" />
      </div>
    );
  }

  return (
    <div className="space-y-4">
      {/* Attendance Settings */}
      <Card>
        <CardHeader>
          <CardTitle className="text-base flex items-center gap-2">
            <Clock className="w-5 h-5" />
            Attendance Settings
          </CardTitle>
        </CardHeader>
        <CardContent>
          <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
            <div className="space-y-4">
              <div className="flex items-center justify-between p-3 bg-gray-50 rounded-lg">
                <div>
                  <p className="font-medium text-gray-900">Late Threshold</p>
                  <p className="text-sm text-gray-500">Minutes after shift start to mark as late</p>
                </div>
                <Badge variant="secondary" className="text-lg">{settings?.late_threshold_minutes || 15} min</Badge>
              </div>
              <div className="flex items-center justify-between p-3 bg-gray-50 rounded-lg">
                <div>
                  <p className="font-medium text-gray-900">Checkout Gap</p>
                  <p className="text-sm text-gray-500">Hours after check-in to trigger checkout</p>
                </div>
                <Badge variant="secondary" className="text-lg">{settings?.checkout_gap_hours || 4} hrs</Badge>
              </div>
              <div className="flex items-center justify-between p-3 bg-gray-50 rounded-lg">
                <div>
                  <p className="font-medium text-gray-900">Standard Work Hours</p>
                  <p className="text-sm text-gray-500">Hours for overtime calculation</p>
                </div>
                <Badge variant="secondary" className="text-lg">{settings?.standard_work_hours || 8} hrs</Badge>
              </div>
            </div>
            <div className="space-y-4">
              <div className="flex items-center justify-between p-3 bg-gray-50 rounded-lg">
                <div>
                  <p className="font-medium text-gray-900">Cooldown Period</p>
                  <p className="text-sm text-gray-500">Seconds between attendance logs</p>
                </div>
                <Badge variant="secondary" className="text-lg">{settings?.attendance_cooldown_seconds || 60} sec</Badge>
              </div>
              <div className="flex items-center justify-between p-3 bg-gray-50 rounded-lg">
                <div>
                  <p className="font-medium text-gray-900">Save Snapshots</p>
                  <p className="text-sm text-gray-500">Save photos on check-in/out</p>
                </div>
                <Badge variant={settings?.save_attendance_snapshot ? 'default' : 'secondary'}>
                  {settings?.save_attendance_snapshot ? 'Enabled' : 'Disabled'}
                </Badge>
              </div>
            </div>
          </div>
        </CardContent>
      </Card>

      {/* Recognition Settings */}
      <Card>
        <CardHeader>
          <CardTitle className="text-base flex items-center gap-2">
            <Eye className="w-5 h-5" />
            Recognition Settings
          </CardTitle>
        </CardHeader>
        <CardContent>
          <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
            <div className="p-3 bg-gray-50 rounded-lg text-center">
              <p className="text-sm text-gray-500 mb-1">Model</p>
              <p className="font-semibold">{settings?.recognition_model || 'buffalo_l'}</p>
            </div>
            <div className="p-3 bg-gray-50 rounded-lg text-center">
              <p className="text-sm text-gray-500 mb-1">Detection Confidence</p>
              <p className="font-semibold">{settings?.detection_confidence || 0.5}</p>
            </div>
            <div className="p-3 bg-gray-50 rounded-lg text-center">
              <p className="text-sm text-gray-500 mb-1">Recognition Threshold</p>
              <p className="font-semibold">{settings?.recognition_threshold || 0.4}</p>
            </div>
            <div className="p-3 bg-gray-50 rounded-lg text-center">
              <p className="text-sm text-gray-500 mb-1">TensorRT</p>
              <Badge variant={settings?.use_tensorrt ? 'default' : 'secondary'}>
                {settings?.use_tensorrt ? 'Enabled' : 'Disabled'}
              </Badge>
            </div>
            <div className="p-3 bg-gray-50 rounded-lg text-center">
              <p className="text-sm text-gray-500 mb-1">GPU FAISS</p>
              <Badge variant={settings?.faiss_use_gpu ? 'default' : 'secondary'}>
                {settings?.faiss_use_gpu ? 'Enabled' : 'Disabled'}
              </Badge>
            </div>
            <div className="p-3 bg-gray-50 rounded-lg text-center">
              <p className="text-sm text-gray-500 mb-1">Frame Skip</p>
              <p className="font-semibold">{settings?.frame_skip || 1}</p>
            </div>
          </div>
        </CardContent>
      </Card>
    </div>
  );
}

// Live Stream Tab
function LiveStreamTab({ token }: { token: string }) {
  const [streamStatus, setStreamStatus] = useState<any>(null);
  const [cameras, setCameras] = useState<any[]>([]);
  const [selectedCamera, setSelectedCamera] = useState<number | null>(null);
  const [isFullscreen, setIsFullscreen] = useState(false);
  const [recentActivity, setRecentActivity] = useState<any[]>([]);
  const [wsConnected, setWsConnected] = useState(false);

  // Fetch stream status and cameras
  useEffect(() => {
    const fetchData = async () => {
      try {
        const [statusData, camerasData] = await Promise.all([
          apiFetch('/stream/status', token),
          apiFetch('/cameras', token),
        ]);
        setStreamStatus(statusData);
        setCameras(camerasData.cameras || []);
      } catch (err) {
        console.error('Error fetching stream data:', err);
      }
    };
    fetchData();
    const interval = setInterval(fetchData, 5000);
    return () => clearInterval(interval);
  }, [token]);

  // WebSocket for real-time attendance updates
  useEffect(() => {
    const wsUrl = API_BASE_URL.replace('http', 'ws').replace('/api', '') + '/api/stream/ws/attendance';
    let ws: WebSocket | null = null;
    let reconnectTimeout: NodeJS.Timeout;

    const connect = () => {
      ws = new WebSocket(wsUrl);

      ws.onopen = () => {
        setWsConnected(true);
        console.log('Attendance WebSocket connected');
      };

      ws.onmessage = (event) => {
        try {
          const data = JSON.parse(event.data);
          if (data.type === 'attendance') {
            setRecentActivity(prev => [data, ...prev].slice(0, 10));
          }
        } catch {}
      };

      ws.onclose = () => {
        setWsConnected(false);
        reconnectTimeout = setTimeout(connect, 3000);
      };

      ws.onerror = () => {
        ws?.close();
      };
    };

    connect();
    return () => {
      ws?.close();
      clearTimeout(reconnectTimeout);
    };
  }, []);

  const streamUrl = selectedCamera
    ? `${API_BASE_URL}/stream/mjpeg/camera/${selectedCamera}`
    : `${API_BASE_URL}/stream/mjpeg`;

  const handleStartStream = async () => {
    try {
      await apiFetch('/stream/start', token);
    } catch (err) {
      console.error('Failed to start stream:', err);
    }
  };

  const handleStopStream = async () => {
    try {
      await apiFetch('/stream/stop', token);
    } catch (err) {
      console.error('Failed to stop stream:', err);
    }
  };

  return (
    <div className="space-y-4">
      {/* Stream Controls */}
      <div className="flex items-center justify-between">
        <div className="flex items-center gap-4">
          <Badge variant={streamStatus?.running ? 'default' : 'secondary'} className="text-sm">
            {streamStatus?.running ? 'Stream Active' : 'Stream Stopped'}
          </Badge>
          {streamStatus?.running && (
            <>
              <Badge variant="outline">{streamStatus?.fps || 0} FPS</Badge>
              <Badge variant="outline">{streamStatus?.num_cameras || 0} Cameras</Badge>
              <Badge variant={wsConnected ? 'default' : 'secondary'}>
                {wsConnected ? 'Live Updates' : 'Connecting...'}
              </Badge>
            </>
          )}
        </div>
        <div className="flex items-center gap-2">
          {!streamStatus?.running ? (
            <Button onClick={handleStartStream}>
              <Play className="w-4 h-4 mr-2" />
              Start Stream
            </Button>
          ) : (
            <Button variant="outline" onClick={handleStopStream}>
              <Pause className="w-4 h-4 mr-2" />
              Stop Stream
            </Button>
          )}
        </div>
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-4 gap-4">
        {/* Main Stream View */}
        <div className={cn("lg:col-span-3", isFullscreen && "fixed inset-0 z-50 bg-black p-4")}>
          <Card className="h-full">
            <CardHeader className="flex flex-row items-center justify-between py-3">
              <CardTitle className="text-base flex items-center gap-2">
                <Video className="w-5 h-5" />
                {selectedCamera ? cameras.find(c => c.id === selectedCamera)?.name || 'Camera' : 'All Cameras'}
              </CardTitle>
              <div className="flex items-center gap-2">
                <select
                  className="text-sm border rounded px-2 py-1"
                  value={selectedCamera || ''}
                  onChange={(e) => setSelectedCamera(e.target.value ? Number(e.target.value) : null)}
                >
                  <option value="">All Cameras (Tiled)</option>
                  {cameras.filter(c => c.enabled).map((cam) => (
                    <option key={cam.id} value={cam.id}>{cam.name}</option>
                  ))}
                </select>
                <Button
                  variant="ghost"
                  size="sm"
                  onClick={() => setIsFullscreen(!isFullscreen)}
                >
                  <Maximize2 className="w-4 h-4" />
                </Button>
              </div>
            </CardHeader>
            <CardContent className="p-0">
              {streamStatus?.running ? (
                <div className="relative bg-black aspect-video">
                  <img
                    src={streamUrl}
                    alt="Live Stream"
                    className="w-full h-full object-contain"
                    onError={(e) => {
                      (e.target as HTMLImageElement).style.display = 'none';
                    }}
                  />
                  {/* Overlay info */}
                  <div className="absolute top-2 left-2 flex items-center gap-2">
                    <div className="bg-red-600 text-white text-xs px-2 py-1 rounded flex items-center gap-1">
                      <span className="w-2 h-2 bg-white rounded-full animate-pulse" />
                      LIVE
                    </div>
                  </div>
                  <div className="absolute bottom-2 right-2 bg-black/60 text-white text-xs px-2 py-1 rounded">
                    {streamStatus?.fps || 0} FPS
                  </div>
                </div>
              ) : (
                <div className="aspect-video bg-gray-900 flex items-center justify-center">
                  <div className="text-center text-gray-400">
                    <Video className="w-16 h-16 mx-auto mb-4 opacity-50" />
                    <p className="text-lg mb-2">Stream Not Active</p>
                    <p className="text-sm mb-4">Click "Start Stream" to begin viewing</p>
                    <Button onClick={handleStartStream}>
                      <Play className="w-4 h-4 mr-2" />
                      Start Stream
                    </Button>
                  </div>
                </div>
              )}
            </CardContent>
          </Card>
        </div>

        {/* Sidebar - Recent Activity */}
        {!isFullscreen && (
          <div className="lg:col-span-1">
            <Card className="h-full">
              <CardHeader className="py-3">
                <CardTitle className="text-base flex items-center gap-2">
                  <Clock className="w-5 h-5" />
                  Live Activity
                </CardTitle>
              </CardHeader>
              <CardContent className="p-0">
                <div className="max-h-[500px] overflow-y-auto">
                  {recentActivity.length === 0 ? (
                    <div className="text-center py-8 text-gray-500">
                      <UserCheck className="w-10 h-10 mx-auto mb-2 opacity-50" />
                      <p className="text-sm">Waiting for check-ins...</p>
                    </div>
                  ) : (
                    <div className="divide-y">
                      {recentActivity.map((activity, idx) => (
                        <div key={idx} className="p-3 hover:bg-gray-50">
                          <div className="flex items-center gap-3">
                            <div className={cn(
                              "w-8 h-8 rounded-full flex items-center justify-center",
                              activity.action === 'check_in' ? "bg-green-100" : "bg-blue-100"
                            )}>
                              {activity.action === 'check_in' ? (
                                <UserCheck className="w-4 h-4 text-green-600" />
                              ) : (
                                <UserX className="w-4 h-4 text-blue-600" />
                              )}
                            </div>
                            <div className="flex-1 min-w-0">
                              <p className="text-sm font-medium text-gray-900 truncate">
                                {activity.employee_name}
                              </p>
                              <p className="text-xs text-gray-500">
                                {activity.action === 'check_in' ? 'Checked In' : 'Checked Out'}
                              </p>
                            </div>
                            <span className="text-xs text-gray-400">
                              {new Date(activity.timestamp).toLocaleTimeString()}
                            </span>
                          </div>
                        </div>
                      ))}
                    </div>
                  )}
                </div>
              </CardContent>
            </Card>

            {/* Camera Status */}
            <Card className="mt-4">
              <CardHeader className="py-3">
                <CardTitle className="text-base">Camera Status</CardTitle>
              </CardHeader>
              <CardContent className="p-0">
                <div className="divide-y">
                  {cameras.filter(c => c.enabled).map((cam) => (
                    <div key={cam.id} className="p-3 flex items-center justify-between">
                      <div className="flex items-center gap-2">
                        <Camera className={cn(
                          "w-4 h-4",
                          cam.is_online ? "text-green-500" : "text-gray-400"
                        )} />
                        <span className="text-sm">{cam.name}</span>
                      </div>
                      <Badge variant={cam.is_online ? 'default' : 'secondary'} className="text-xs">
                        {cam.is_online ? 'Online' : 'Offline'}
                      </Badge>
                    </div>
                  ))}
                </div>
              </CardContent>
            </Card>
          </div>
        )}
      </div>
    </div>
  );
}

function Dashboard() {
  const { user, logout, token } = useAuth();
  const [currentTime, setCurrentTime] = useState(new Date());
  const [activeTab, setActiveTab] = useState('dashboard');
  const [sidebarOpen, setSidebarOpen] = useState(true);

  useEffect(() => {
    const timer = setInterval(() => setCurrentTime(new Date()), 1000);
    return () => clearInterval(timer);
  }, []);

  const navItems = [
    { id: 'dashboard', icon: BarChart3, label: 'Dashboard' },
    { id: 'livestream', icon: Video, label: 'Live Stream' },
    { id: 'employees', icon: Users, label: 'Employees' },
    { id: 'attendance', icon: Calendar, label: 'Attendance' },
    { id: 'reports', icon: TrendingUp, label: 'Reports' },
    { id: 'departments', icon: Building2, label: 'Departments' },
    { id: 'cameras', icon: Camera, label: 'Cameras' },
    { id: 'settings', icon: Settings, label: 'Settings' },
  ];

  return (
    <div className="min-h-screen bg-gray-50 flex">
      {/* Sidebar */}
      <aside className={cn(
        "fixed inset-y-0 left-0 z-50 w-64 bg-white border-r border-gray-200 transform transition-transform duration-200 ease-in-out lg:relative lg:translate-x-0",
        sidebarOpen ? "translate-x-0" : "-translate-x-full"
      )}>
        <div className="flex flex-col h-full">
          <div className="flex items-center gap-3 px-6 py-5 border-b border-gray-200">
            <div className="w-10 h-10 bg-blue-600 rounded-xl flex items-center justify-center">
              <Clock className="w-5 h-5 text-white" />
            </div>
            <div>
              <h1 className="font-bold text-gray-900">Attendance</h1>
              <p className="text-xs text-gray-500">Management System</p>
            </div>
          </div>

          <nav className="flex-1 px-3 py-4 space-y-1 overflow-y-auto">
            {navItems.map((item) => (
              <button
                key={item.id}
                onClick={() => setActiveTab(item.id)}
                className={cn(
                  "w-full flex items-center gap-3 px-3 py-2.5 rounded-lg text-sm font-medium transition-colors",
                  activeTab === item.id ? "bg-blue-50 text-blue-600" : "text-gray-600 hover:bg-gray-100"
                )}
              >
                <item.icon className="w-5 h-5" />
                {item.label}
              </button>
            ))}
          </nav>

          <div className="p-4 border-t border-gray-200">
            <div className="flex items-center justify-between">
              <div className="flex items-center gap-3">
                <div className="w-9 h-9 bg-gray-200 rounded-full flex items-center justify-center">
                  <span className="text-sm font-medium text-gray-600">{user?.username?.charAt(0).toUpperCase()}</span>
                </div>
                <div>
                  <p className="text-sm font-medium text-gray-900">{user?.username}</p>
                  <p className="text-xs text-gray-500 capitalize">{user?.role}</p>
                </div>
              </div>
              <button onClick={logout} className="p-2 text-gray-400 hover:text-gray-600 rounded-lg hover:bg-gray-100">
                <LogOut className="w-4 h-4" />
              </button>
            </div>
          </div>
        </div>
      </aside>

      {/* Main Content */}
      <main className="flex-1 min-w-0">
        <header className="sticky top-0 z-40 bg-white border-b border-gray-200 px-6 py-4">
          <div className="flex items-center justify-between">
            <div className="flex items-center gap-4">
              <button
                onClick={() => setSidebarOpen(!sidebarOpen)}
                className="lg:hidden p-2 text-gray-400 hover:text-gray-600 rounded-lg hover:bg-gray-100"
              >
                {sidebarOpen ? <X className="w-5 h-5" /> : <Menu className="w-5 h-5" />}
              </button>
              <div>
                <h2 className="text-xl font-bold text-gray-900">
                  {navItems.find(n => n.id === activeTab)?.label || 'Dashboard'}
                </h2>
                <p className="text-sm text-gray-500">
                  {currentTime.toLocaleDateString('en-US', { weekday: 'long', year: 'numeric', month: 'long', day: 'numeric' })}
                </p>
              </div>
            </div>
            <div className="text-right">
              <p className="text-2xl font-bold text-gray-900 tabular-nums">
                {currentTime.toLocaleTimeString('en-US', { hour: '2-digit', minute: '2-digit', second: '2-digit' })}
              </p>
            </div>
          </div>
        </header>

        <div className="p-6">
          {activeTab === 'dashboard' && token && <DashboardTab token={token} />}
          {activeTab === 'livestream' && token && <LiveStreamTab token={token} />}
          {activeTab === 'employees' && token && <EmployeesTab token={token} />}
          {activeTab === 'attendance' && token && <AttendanceTab token={token} />}
          {activeTab === 'reports' && token && <ReportsTab token={token} />}
          {activeTab === 'departments' && token && <DepartmentsTab token={token} />}
          {activeTab === 'cameras' && token && <CamerasTab token={token} />}
          {activeTab === 'settings' && token && <SettingsTab token={token} />}
        </div>
      </main>
    </div>
  );
}

function AppContent() {
  const { isAuthenticated, isLoading } = useAuth();

  if (isLoading) {
    return (
      <div className="min-h-screen bg-gray-50 flex items-center justify-center">
        <div className="text-center">
          <div className="w-12 h-12 border-4 border-blue-600 border-t-transparent rounded-full animate-spin mx-auto mb-4" />
          <p className="text-gray-500">Loading...</p>
        </div>
      </div>
    );
  }

  return isAuthenticated ? <Dashboard /> : <LoginPage />;
}

export default function App() {
  return (
    <AuthProvider>
      <AppContent />
    </AuthProvider>
  );
}
