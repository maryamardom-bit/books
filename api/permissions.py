from rest_framework import permissions


class IsOwnerOrAdmin(permissions.BasePermission):
    """
    Permission to only allow owners of an object or admins to access it.
    """
    
    def has_object_permission(self, request, view, obj):
        # Admin has full access
        if request.user.is_staff:
            return True
        
        # Check if object has user attribute
        if hasattr(obj, 'user'):
            return obj.user == request.user
        
        # Check if object has order with user
        if hasattr(obj, 'order') and hasattr(obj.order, 'user'):
            return obj.order.user == request.user
        
        return False


class IsOwnerOrAdminOrReadOnly(permissions.BasePermission):
    """
    Permission to allow read-only access to everyone,
    but only owners/admins can edit.
    """
    
    def has_permission(self, request, view):
        # Allow read-only for everyone
        if request.method in permissions.SAFE_METHODS:
            return True
        
        # Write requires authentication
        return request.user and request.user.is_authenticated
    
    def has_object_permission(self, request, view, obj):
        # Read-only for everyone
        if request.method in permissions.SAFE_METHODS:
            return True
        
        # Admin has full access
        if request.user.is_staff:
            return True
        
        # Check ownership
        if hasattr(obj, 'user'):
            return obj.user == request.user
        
        return False


class IsAdminOrReadOnly(permissions.BasePermission):
    """
    Permission to allow read-only access to everyone,
    but only admins can edit.
    """
    
    def has_permission(self, request, view):
        # Allow read-only for everyone
        if request.method in permissions.SAFE_METHODS:
            return True
        
        # Write requires admin
        return request.user and request.user.is_staff


class IsProductOwnerOrAdmin(permissions.BasePermission):
    """
    Permission for product-related operations.
    """
    
    def has_permission(self, request, view):
        # Everyone can view
        if request.method in permissions.SAFE_METHODS:
            return True
        
        # Write requires authentication
        return request.user and request.user.is_authenticated
    
    def has_object_permission(self, request, view, obj):
        # Read-only for everyone
        if request.method in permissions.SAFE_METHODS:
            return True
        
        # Admin has full access
        if request.user.is_staff:
            return True
        
        # For Comment, check if user is the author
        if hasattr(obj, 'author') and hasattr(obj.author, 'id'):
            return obj.author.id == request.user.id
        
        return False


class IsOrderOwnerOrAdmin(permissions.BasePermission):
    """
    Permission for order-related operations.
    Only order owner or admin can access.
    """
    
    def has_permission(self, request, view):
        # Must be authenticated
        return request.user and request.user.is_authenticated
    
    def has_object_permission(self, request, view, obj):
        # Admin has full access
        if request.user.is_staff:
            return True
        
        # Check if object is Order
        if hasattr(obj, 'user'):
            return obj.user == request.user
        
        # Check if object is OrderItem
        if hasattr(obj, 'order') and hasattr(obj.order, 'user'):
            return obj.order.user == request.user
        
        return False