"""
api/routes/roles.py

API endpoints for custom roles and permissions management.
"""

from fastapi import APIRouter, Depends, HTTPException
from typing import List, Optional
from pydantic import BaseModel
from api.auth import get_current_user
from db.client import db
from db.ops.roles import (
    create_role, delete_role, get_role, get_roles,
    update_role_permissions, assign_role, remove_role,
    get_user_roles, get_users_with_role, has_permission,
    PERMISSIONS
)

router = APIRouter(prefix="/api/groups")


class RoleCreate(BaseModel):
    name: str
    color: str = '#64748b'
    permissions: dict = {}


class RoleUpdate(BaseModel):
    color: Optional[str] = None
    permissions: Optional[dict] = None


class RoleAssign(BaseModel):
    user_id: int
    expires_at: Optional[str] = None  # ISO format datetime


@router.get("/{chat_id}/roles")
async def list_roles(chat_id: int, user: dict = Depends(get_current_user)):
    """Get all roles for a group."""
    roles = await get_roles(chat_id)
    return {'chat_id': chat_id, 'roles': roles}


@router.post("/{chat_id}/roles")
async def create_role_endpoint(
    chat_id: int,
    data: RoleCreate,
    user: dict = Depends(get_current_user)
):
    """Create a new role."""
    # Validate permissions
    for perm in data.permissions.keys():
        if perm not in PERMISSIONS:
            raise HTTPException(400, f"Invalid permission: {perm}")
    
    role_id = await create_role(
        chat_id, data.name, data.color, data.permissions
    )
    return {
        'id': role_id,
        'chat_id': chat_id,
        'name': data.name,
        'color': data.color,
        'permissions': data.permissions
    }


@router.get("/{chat_id}/roles/{role_id}")
async def get_role_endpoint(
    chat_id: int,
    role_id: int,
    user: dict = Depends(get_current_user)
):
    """Get a specific role."""
    role = await get_role(chat_id, role_id)
    if not role:
        raise HTTPException(404, "Role not found")
    return role


@router.put("/{chat_id}/roles/{role_id}")
async def update_role_endpoint(
    chat_id: int,
    role_id: int,
    data: RoleUpdate,
    user: dict = Depends(get_current_user)
):
    """Update role permissions or color."""
    if data.permissions is not None:
        # Validate permissions
        for perm in data.permissions.keys():
            if perm not in PERMISSIONS:
                raise HTTPException(400, f"Invalid permission: {perm}")
        
        success = await update_role_permissions(
            chat_id, role_id, data.permissions
        )
        if not success:
            raise HTTPException(404, "Role not found")
    
    role = await get_role(chat_id, role_id)
    return role


@router.delete("/{chat_id}/roles/{role_id}")
async def delete_role_endpoint(
    chat_id: int,
    role_id: int,
    user: dict = Depends(get_current_user)
):
    """Delete a role."""
    success = await delete_role(chat_id, role_id)
    if not success:
        raise HTTPException(404, "Role not found")
    return {'status': 'deleted'}


@router.get("/{chat_id}/roles/{role_id}/users")
async def get_role_users(
    chat_id: int,
    role_id: int,
    user: dict = Depends(get_current_user)
):
    """Get all users with a specific role."""
    users = await get_users_with_role(chat_id, role_id)
    return {
        'chat_id': chat_id,
        'role_id': role_id,
        'users': users
    }


@router.get("/{chat_id}/users/{user_id}/roles")
async def get_user_roles_endpoint(
    chat_id: int,
    user_id: int,
    user: dict = Depends(get_current_user)
):
    """Get all roles assigned to a user."""
    roles = await get_user_roles(user_id, chat_id)
    return {
        'chat_id': chat_id,
        'user_id': user_id,
        'roles': roles
    }


@router.post("/{chat_id}/users/{user_id}/roles")
async def assign_role_endpoint(
    chat_id: int,
    user_id: int,
    data: RoleAssign,
    user: dict = Depends(get_current_user)
):
    """Assign a role to a user."""
    from datetime import datetime
    
    expires = None
    if data.expires_at:
        try:
            expires = datetime.fromisoformat(data.expires_at.replace('Z', '+00:00'))
        except ValueError:
            raise HTTPException(400, "Invalid expires_at format")
    
    success = await assign_role(
        user_id, chat_id, data.role_id, 
        granted_by=user.get('id'),
        expires_at=expires
    )
    if not success:
        raise HTTPException(400, "Failed to assign role")
    
    return {'status': 'assigned'}


@router.delete("/{chat_id}/users/{user_id}/roles/{role_id}")
async def remove_role_endpoint(
    chat_id: int,
    user_id: int,
    role_id: int,
    user: dict = Depends(get_current_user)
):
    """Remove a role from a user."""
    success = await remove_role(user_id, chat_id, role_id)
    if not success:
        raise HTTPException(404, "Role assignment not found")
    return {'status': 'removed'}


@router.get("/{chat_id}/users/{user_id}/permissions")
async def get_user_permissions_endpoint(
    chat_id: int,
    user_id: int,
    user: dict = Depends(get_current_user)
):
    """Get all permissions for a user."""
    from db.ops.roles import get_all_user_permissions
    
    permissions = await get_all_user_permissions(user_id, chat_id)
    return {
        'chat_id': chat_id,
        'user_id': user_id,
        'permissions': permissions,
        'available_permissions': list(PERMISSIONS)
    }
