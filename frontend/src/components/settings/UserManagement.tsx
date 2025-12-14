import { useState, useEffect } from "react"
import {
  Users,
  UserPlus,
  Trash2,
  Edit,
  Key,
  Loader2,
  Check,
  X,
  Shield,
  User,
} from "lucide-react"

import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card"
import { Button } from "@/components/ui/button"
import { Input } from "@/components/ui/input"
import { Label } from "@/components/ui/label"
import { Badge } from "@/components/ui/badge"
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
  DialogTrigger,
} from "@/components/ui/dialog"
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select"
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "@/components/ui/table"
import {
  AlertDialog,
  AlertDialogAction,
  AlertDialogCancel,
  AlertDialogContent,
  AlertDialogDescription,
  AlertDialogFooter,
  AlertDialogHeader,
  AlertDialogTitle,
} from "@/components/ui/alert-dialog"
import api from "@/services/api"
import { useAuth } from "@/contexts/AuthContext"

interface UserData {
  id: number
  username: string
  email: string | null
  role: string
  is_active: boolean
  created_at: string
  updated_at: string
  last_login: string | null
}

export function UserManagement() {
  const { user: currentUser } = useAuth()
  const [users, setUsers] = useState<UserData[]>([])
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)

  // Create user dialog
  const [showCreateDialog, setShowCreateDialog] = useState(false)
  const [createForm, setCreateForm] = useState({
    username: "",
    email: "",
    password: "",
    role: "user",
  })
  const [creating, setCreating] = useState(false)

  // Edit user dialog
  const [editingUser, setEditingUser] = useState<UserData | null>(null)
  const [editForm, setEditForm] = useState({
    email: "",
    role: "",
    is_active: true,
  })
  const [editing, setEditing] = useState(false)

  // Reset password dialog
  const [resetPasswordUser, setResetPasswordUser] = useState<UserData | null>(null)
  const [newPassword, setNewPassword] = useState("")
  const [resettingPassword, setResettingPassword] = useState(false)

  // Delete confirmation
  const [deletingUser, setDeletingUser] = useState<UserData | null>(null)
  const [deleting, setDeleting] = useState(false)

  useEffect(() => {
    fetchUsers()
  }, [])

  const fetchUsers = async () => {
    setLoading(true)
    setError(null)
    try {
      const response = await api.users.list()
      setUsers(response.users)
    } catch (err) {
      console.error("Failed to fetch users", err)
      setError("Failed to load users")
    } finally {
      setLoading(false)
    }
  }

  const handleCreateUser = async () => {
    setCreating(true)
    try {
      await api.users.create({
        username: createForm.username,
        email: createForm.email || undefined,
        password: createForm.password,
        role: createForm.role,
      })
      setShowCreateDialog(false)
      setCreateForm({ username: "", email: "", password: "", role: "user" })
      await fetchUsers()
    } catch (err: unknown) {
      const error = err as { response?: { data?: { detail?: string } } }
      alert(error.response?.data?.detail || "Failed to create user")
    } finally {
      setCreating(false)
    }
  }

  const handleEditUser = async () => {
    if (!editingUser) return
    setEditing(true)
    try {
      await api.users.update(editingUser.id, {
        email: editForm.email || undefined,
        role: editForm.role,
        is_active: editForm.is_active,
      })
      setEditingUser(null)
      await fetchUsers()
    } catch (err: unknown) {
      const error = err as { response?: { data?: { detail?: string } } }
      alert(error.response?.data?.detail || "Failed to update user")
    } finally {
      setEditing(false)
    }
  }

  const handleResetPassword = async () => {
    if (!resetPasswordUser) return
    setResettingPassword(true)
    try {
      await api.users.resetPassword(resetPasswordUser.id, newPassword)
      setResetPasswordUser(null)
      setNewPassword("")
      alert("Password reset successfully")
    } catch (err: unknown) {
      const error = err as { response?: { data?: { detail?: string } } }
      alert(error.response?.data?.detail || "Failed to reset password")
    } finally {
      setResettingPassword(false)
    }
  }

  const handleDeleteUser = async () => {
    if (!deletingUser) return
    setDeleting(true)
    try {
      await api.users.delete(deletingUser.id)
      setDeletingUser(null)
      await fetchUsers()
    } catch (err: unknown) {
      const error = err as { response?: { data?: { detail?: string } } }
      alert(error.response?.data?.detail || "Failed to delete user")
    } finally {
      setDeleting(false)
    }
  }

  const openEditDialog = (user: UserData) => {
    setEditingUser(user)
    setEditForm({
      email: user.email || "",
      role: user.role,
      is_active: user.is_active,
    })
  }

  const formatDate = (dateString: string | null) => {
    if (!dateString) return "Never"
    return new Date(dateString).toLocaleString()
  }

  return (
    <Card>
      <CardHeader>
        <div className="flex items-center justify-between">
          <div>
            <CardTitle className="flex items-center gap-2">
              <Users className="h-5 w-5" />
              User Management
            </CardTitle>
            <CardDescription>
              Manage user accounts and permissions
            </CardDescription>
          </div>
          <Dialog open={showCreateDialog} onOpenChange={setShowCreateDialog}>
            <DialogTrigger asChild>
              <Button>
                <UserPlus className="mr-2 h-4 w-4" />
                Add User
              </Button>
            </DialogTrigger>
            <DialogContent>
              <DialogHeader>
                <DialogTitle>Create New User</DialogTitle>
                <DialogDescription>
                  Add a new user account to the system.
                </DialogDescription>
              </DialogHeader>
              <div className="space-y-4 py-4">
                <div className="space-y-2">
                  <Label htmlFor="username">Username</Label>
                  <Input
                    id="username"
                    value={createForm.username}
                    onChange={(e) =>
                      setCreateForm({ ...createForm, username: e.target.value })
                    }
                    placeholder="Enter username"
                  />
                </div>
                <div className="space-y-2">
                  <Label htmlFor="email">Email (optional)</Label>
                  <Input
                    id="email"
                    type="email"
                    value={createForm.email}
                    onChange={(e) =>
                      setCreateForm({ ...createForm, email: e.target.value })
                    }
                    placeholder="Enter email"
                  />
                </div>
                <div className="space-y-2">
                  <Label htmlFor="password">Password</Label>
                  <Input
                    id="password"
                    type="password"
                    value={createForm.password}
                    onChange={(e) =>
                      setCreateForm({ ...createForm, password: e.target.value })
                    }
                    placeholder="Enter password (min 8 chars)"
                  />
                </div>
                <div className="space-y-2">
                  <Label htmlFor="role">Role</Label>
                  <Select
                    value={createForm.role}
                    onValueChange={(value) =>
                      setCreateForm({ ...createForm, role: value })
                    }
                  >
                    <SelectTrigger>
                      <SelectValue placeholder="Select role" />
                    </SelectTrigger>
                    <SelectContent>
                      <SelectItem value="user">
                        <div className="flex items-center gap-2">
                          <User className="h-4 w-4" />
                          User (View only)
                        </div>
                      </SelectItem>
                      <SelectItem value="admin">
                        <div className="flex items-center gap-2">
                          <Shield className="h-4 w-4" />
                          Admin (Full access)
                        </div>
                      </SelectItem>
                    </SelectContent>
                  </Select>
                </div>
              </div>
              <DialogFooter>
                <Button
                  variant="outline"
                  onClick={() => setShowCreateDialog(false)}
                >
                  Cancel
                </Button>
                <Button
                  onClick={handleCreateUser}
                  disabled={
                    creating ||
                    !createForm.username ||
                    !createForm.password ||
                    createForm.password.length < 8
                  }
                >
                  {creating ? (
                    <Loader2 className="mr-2 h-4 w-4 animate-spin" />
                  ) : (
                    <UserPlus className="mr-2 h-4 w-4" />
                  )}
                  Create User
                </Button>
              </DialogFooter>
            </DialogContent>
          </Dialog>
        </div>
      </CardHeader>
      <CardContent>
        {loading ? (
          <div className="flex h-32 items-center justify-center">
            <Loader2 className="h-6 w-6 animate-spin" />
          </div>
        ) : error ? (
          <p className="text-center text-destructive">{error}</p>
        ) : (
          <Table>
            <TableHeader>
              <TableRow>
                <TableHead>Username</TableHead>
                <TableHead>Email</TableHead>
                <TableHead>Role</TableHead>
                <TableHead>Status</TableHead>
                <TableHead>Last Login</TableHead>
                <TableHead className="text-right">Actions</TableHead>
              </TableRow>
            </TableHeader>
            <TableBody>
              {users.map((user) => (
                <TableRow key={user.id}>
                  <TableCell className="font-medium">
                    {user.username}
                    {user.id === currentUser?.id && (
                      <Badge variant="outline" className="ml-2 text-xs">
                        You
                      </Badge>
                    )}
                  </TableCell>
                  <TableCell>{user.email || "-"}</TableCell>
                  <TableCell>
                    <Badge
                      variant={user.role === "admin" ? "default" : "secondary"}
                    >
                      {user.role === "admin" ? (
                        <Shield className="mr-1 h-3 w-3" />
                      ) : (
                        <User className="mr-1 h-3 w-3" />
                      )}
                      {user.role}
                    </Badge>
                  </TableCell>
                  <TableCell>
                    {user.is_active ? (
                      <Badge
                        variant="outline"
                        className="border-green-500 text-green-500"
                      >
                        <Check className="mr-1 h-3 w-3" />
                        Active
                      </Badge>
                    ) : (
                      <Badge
                        variant="outline"
                        className="border-red-500 text-red-500"
                      >
                        <X className="mr-1 h-3 w-3" />
                        Inactive
                      </Badge>
                    )}
                  </TableCell>
                  <TableCell className="text-sm text-muted-foreground">
                    {formatDate(user.last_login)}
                  </TableCell>
                  <TableCell className="text-right">
                    <div className="flex justify-end gap-1">
                      <Button
                        variant="ghost"
                        size="icon"
                        onClick={() => openEditDialog(user)}
                        title="Edit user"
                      >
                        <Edit className="h-4 w-4" />
                      </Button>
                      <Button
                        variant="ghost"
                        size="icon"
                        onClick={() => setResetPasswordUser(user)}
                        title="Reset password"
                      >
                        <Key className="h-4 w-4" />
                      </Button>
                      <Button
                        variant="ghost"
                        size="icon"
                        onClick={() => setDeletingUser(user)}
                        disabled={user.id === currentUser?.id}
                        title="Delete user"
                      >
                        <Trash2 className="h-4 w-4 text-destructive" />
                      </Button>
                    </div>
                  </TableCell>
                </TableRow>
              ))}
            </TableBody>
          </Table>
        )}

        {/* Edit User Dialog */}
        <Dialog open={!!editingUser} onOpenChange={() => setEditingUser(null)}>
          <DialogContent>
            <DialogHeader>
              <DialogTitle>Edit User: {editingUser?.username}</DialogTitle>
              <DialogDescription>
                Update user settings and permissions.
              </DialogDescription>
            </DialogHeader>
            <div className="space-y-4 py-4">
              <div className="space-y-2">
                <Label htmlFor="edit-email">Email</Label>
                <Input
                  id="edit-email"
                  type="email"
                  value={editForm.email}
                  onChange={(e) =>
                    setEditForm({ ...editForm, email: e.target.value })
                  }
                  placeholder="Enter email"
                />
              </div>
              <div className="space-y-2">
                <Label htmlFor="edit-role">Role</Label>
                <Select
                  value={editForm.role}
                  onValueChange={(value) =>
                    setEditForm({ ...editForm, role: value })
                  }
                  disabled={editingUser?.id === currentUser?.id}
                >
                  <SelectTrigger>
                    <SelectValue placeholder="Select role" />
                  </SelectTrigger>
                  <SelectContent>
                    <SelectItem value="user">User (View only)</SelectItem>
                    <SelectItem value="admin">Admin (Full access)</SelectItem>
                  </SelectContent>
                </Select>
                {editingUser?.id === currentUser?.id && (
                  <p className="text-xs text-muted-foreground">
                    Cannot change your own role
                  </p>
                )}
              </div>
              <div className="space-y-2">
                <Label htmlFor="edit-status">Status</Label>
                <Select
                  value={editForm.is_active ? "active" : "inactive"}
                  onValueChange={(value) =>
                    setEditForm({ ...editForm, is_active: value === "active" })
                  }
                  disabled={editingUser?.id === currentUser?.id}
                >
                  <SelectTrigger>
                    <SelectValue placeholder="Select status" />
                  </SelectTrigger>
                  <SelectContent>
                    <SelectItem value="active">Active</SelectItem>
                    <SelectItem value="inactive">Inactive</SelectItem>
                  </SelectContent>
                </Select>
                {editingUser?.id === currentUser?.id && (
                  <p className="text-xs text-muted-foreground">
                    Cannot deactivate your own account
                  </p>
                )}
              </div>
            </div>
            <DialogFooter>
              <Button variant="outline" onClick={() => setEditingUser(null)}>
                Cancel
              </Button>
              <Button onClick={handleEditUser} disabled={editing}>
                {editing && <Loader2 className="mr-2 h-4 w-4 animate-spin" />}
                Save Changes
              </Button>
            </DialogFooter>
          </DialogContent>
        </Dialog>

        {/* Reset Password Dialog */}
        <Dialog
          open={!!resetPasswordUser}
          onOpenChange={() => setResetPasswordUser(null)}
        >
          <DialogContent>
            <DialogHeader>
              <DialogTitle>
                Reset Password: {resetPasswordUser?.username}
              </DialogTitle>
              <DialogDescription>
                Set a new password for this user.
              </DialogDescription>
            </DialogHeader>
            <div className="space-y-4 py-4">
              <div className="space-y-2">
                <Label htmlFor="new-password">New Password</Label>
                <Input
                  id="new-password"
                  type="password"
                  value={newPassword}
                  onChange={(e) => setNewPassword(e.target.value)}
                  placeholder="Enter new password (min 8 chars)"
                />
              </div>
            </div>
            <DialogFooter>
              <Button
                variant="outline"
                onClick={() => setResetPasswordUser(null)}
              >
                Cancel
              </Button>
              <Button
                onClick={handleResetPassword}
                disabled={resettingPassword || newPassword.length < 8}
              >
                {resettingPassword && (
                  <Loader2 className="mr-2 h-4 w-4 animate-spin" />
                )}
                Reset Password
              </Button>
            </DialogFooter>
          </DialogContent>
        </Dialog>

        {/* Delete Confirmation */}
        <AlertDialog
          open={!!deletingUser}
          onOpenChange={() => setDeletingUser(null)}
        >
          <AlertDialogContent>
            <AlertDialogHeader>
              <AlertDialogTitle>Delete User</AlertDialogTitle>
              <AlertDialogDescription>
                Are you sure you want to delete user "{deletingUser?.username}"?
                This action cannot be undone.
              </AlertDialogDescription>
            </AlertDialogHeader>
            <AlertDialogFooter>
              <AlertDialogCancel>Cancel</AlertDialogCancel>
              <AlertDialogAction
                onClick={handleDeleteUser}
                className="bg-destructive hover:bg-destructive/90"
              >
                {deleting && <Loader2 className="mr-2 h-4 w-4 animate-spin" />}
                Delete
              </AlertDialogAction>
            </AlertDialogFooter>
          </AlertDialogContent>
        </AlertDialog>
      </CardContent>
    </Card>
  )
}
