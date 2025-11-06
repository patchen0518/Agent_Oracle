"""
Feature flags API router for Oracle application.

Provides REST endpoints for managing feature flags, enabling
gradual rollout and rollback capabilities.
"""

from typing import Dict, Any, Optional, List
from fastapi import APIRouter, HTTPException, Query, Body
from pydantic import BaseModel, Field

from backend.services.feature_flags import get_feature_flag_manager, is_feature_enabled
from backend.services.client_factory import get_client_factory
from backend.utils.logging_config import get_logger


class FeatureFlagStatus(BaseModel):
    """Feature flag status response model."""
    name: str
    state: str
    description: str
    percentage: int = 0
    user_whitelist: List[str] = []
    session_whitelist: List[int] = []
    environment_override: Optional[str] = None
    environment_override_value: Optional[str] = None
    environment_override_active: bool = False
    created_at: Optional[str] = None
    updated_at: Optional[str] = None


class FeatureFlagUpdate(BaseModel):
    """Feature flag update request model."""
    state: Optional[str] = Field(None, description="New state for the flag")
    percentage: Optional[int] = Field(None, ge=0, le=100, description="Percentage for rollout (0-100)")


class WhitelistUpdate(BaseModel):
    """Whitelist update request model."""
    user_id: Optional[str] = Field(None, description="User ID to add/remove")
    session_id: Optional[int] = Field(None, description="Session ID to add/remove")
    action: str = Field(..., description="Action: 'add' or 'remove'")


class FeatureCheckRequest(BaseModel):
    """Feature check request model."""
    flag_name: str
    user_id: Optional[str] = None
    session_id: Optional[int] = None
    context: Optional[Dict[str, Any]] = None


class ClientTestRequest(BaseModel):
    """Client test request model."""
    client_type: str = Field(..., description="Client type: 'langchain' or 'gemini'")


# Create router
router = APIRouter(prefix="/feature-flags", tags=["Feature Flags"])
logger = get_logger("feature_flags_api")


@router.get("/", response_model=Dict[str, FeatureFlagStatus])
async def get_all_feature_flags():
    """Get status of all feature flags."""
    try:
        flag_manager = get_feature_flag_manager()
        all_flags = flag_manager.get_all_flags_status()
        
        response = {}
        for flag_name, flag_data in all_flags.items():
            if flag_data:
                response[flag_name] = FeatureFlagStatus(**flag_data)
        
        return response
        
    except Exception as e:
        logger.error(f"Failed to get feature flags: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Failed to get feature flags: {str(e)}")


@router.get("/{flag_name}", response_model=FeatureFlagStatus)
async def get_feature_flag(flag_name: str):
    """Get status of a specific feature flag."""
    try:
        flag_manager = get_feature_flag_manager()
        flag_status = flag_manager.get_flag_status(flag_name)
        
        if not flag_status:
            raise HTTPException(status_code=404, detail=f"Feature flag '{flag_name}' not found")
        
        return FeatureFlagStatus(**flag_status)
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to get feature flag '{flag_name}': {str(e)}")
        raise HTTPException(status_code=500, detail=f"Failed to get feature flag: {str(e)}")


@router.post("/check")
async def check_feature_enabled(request: FeatureCheckRequest):
    """Check if a feature is enabled for given context."""
    try:
        enabled = is_feature_enabled(
            request.flag_name,
            user_id=request.user_id,
            session_id=request.session_id,
            context=request.context
        )
        
        return {
            "flag_name": request.flag_name,
            "enabled": enabled,
            "user_id": request.user_id,
            "session_id": request.session_id,
            "context": request.context
        }
        
    except Exception as e:
        logger.error(f"Failed to check feature flag '{request.flag_name}': {str(e)}")
        raise HTTPException(status_code=500, detail=f"Failed to check feature flag: {str(e)}")


@router.put("/{flag_name}")
async def update_feature_flag(flag_name: str, update: FeatureFlagUpdate):
    """Update a feature flag configuration."""
    try:
        flag_manager = get_feature_flag_manager()
        
        if not flag_manager.get_flag_status(flag_name):
            raise HTTPException(status_code=404, detail=f"Feature flag '{flag_name}' not found")
        
        success = True
        
        if update.state:
            if update.state == "enabled":
                success = flag_manager.enable_flag(flag_name)
            elif update.state == "disabled":
                success = flag_manager.disable_flag(flag_name)
            elif update.state == "percentage_rollout":
                percentage = update.percentage if update.percentage is not None else 0
                success = flag_manager.set_percentage_rollout(flag_name, percentage)
            else:
                raise HTTPException(status_code=400, detail=f"Invalid state: {update.state}")
        elif update.percentage is not None:
            success = flag_manager.set_percentage_rollout(flag_name, update.percentage)
        
        if not success:
            raise HTTPException(status_code=500, detail=f"Failed to update feature flag")
        
        updated_status = flag_manager.get_flag_status(flag_name)
        return FeatureFlagStatus(**updated_status)
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to update feature flag '{flag_name}': {str(e)}")
        raise HTTPException(status_code=500, detail=f"Failed to update feature flag: {str(e)}")


@router.post("/{flag_name}/whitelist")
async def update_whitelist(flag_name: str, update: WhitelistUpdate):
    """Add or remove users/sessions from feature flag whitelist."""
    try:
        flag_manager = get_feature_flag_manager()
        
        if not flag_manager.get_flag_status(flag_name):
            raise HTTPException(status_code=404, detail=f"Feature flag '{flag_name}' not found")
        
        if update.action not in ["add", "remove"]:
            raise HTTPException(status_code=400, detail="Action must be 'add' or 'remove'")
        
        if not update.user_id and update.session_id is None:
            raise HTTPException(status_code=400, detail="Either user_id or session_id must be provided")
        
        success = False
        if update.action == "add":
            success = flag_manager.add_to_whitelist(flag_name, user_id=update.user_id, session_id=update.session_id)
        else:
            success = flag_manager.remove_from_whitelist(flag_name, user_id=update.user_id, session_id=update.session_id)
        
        if not success:
            raise HTTPException(status_code=500, detail=f"Failed to {update.action} whitelist entry")
        
        updated_status = flag_manager.get_flag_status(flag_name)
        return FeatureFlagStatus(**updated_status)
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to update whitelist for '{flag_name}': {str(e)}")
        raise HTTPException(status_code=500, detail=f"Failed to update whitelist: {str(e)}")


@router.post("/reload")
async def reload_configuration():
    """Reload feature flag configuration from file."""
    try:
        flag_manager = get_feature_flag_manager()
        success = flag_manager.reload_configuration()
        
        if not success:
            raise HTTPException(status_code=500, detail="Failed to reload configuration")
        
        return {"message": "Configuration reloaded successfully"}
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to reload configuration: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Failed to reload configuration: {str(e)}")


@router.get("/client/stats")
async def get_client_stats():
    """Get client factory and feature flag statistics."""
    try:
        client_factory = get_client_factory()
        return client_factory.get_client_stats()
    except Exception as e:
        logger.error(f"Failed to get client stats: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Failed to get client stats: {str(e)}")


@router.post("/client/test")
async def test_client_creation(request: ClientTestRequest):
    """Test client creation for debugging purposes."""
    try:
        client_factory = get_client_factory()
        result = client_factory.test_client_creation(request.client_type)
        
        return result
        
    except Exception as e:
        logger.error(f"Failed to test client creation: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Failed to test client creation: {str(e)}")


@router.get("/client/type")
async def get_client_type(
    session_id: Optional[int] = Query(None, description="Session ID for evaluation"),
    user_id: Optional[str] = Query(None, description="User ID for evaluation")
):
    """Get the client type that would be used for given context."""
    try:
        client_factory = get_client_factory()
        client_type = client_factory.get_client_type(session_id=session_id, user_id=user_id)
        
        return {
            "client_type": client_type,
            "session_id": session_id,
            "user_id": user_id
        }
        
    except Exception as e:
        logger.error(f"Failed to get client type: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Failed to get client type: {str(e)}")


@router.post("/rollout/gradual/{flag_name}")
async def setup_gradual_rollout(
    flag_name: str,
    target_percentage: int = Body(..., ge=0, le=100, description="Target percentage for rollout"),
    step_size: int = Body(10, ge=1, le=50, description="Percentage increase per step")
):
    """Setup gradual rollout for a feature flag."""
    try:
        flag_manager = get_feature_flag_manager()
        
        if not flag_manager.get_flag_status(flag_name):
            raise HTTPException(status_code=404, detail=f"Feature flag '{flag_name}' not found")
        
        current_status = flag_manager.get_flag_status(flag_name)
        current_percentage = current_status.get("percentage", 0)
        
        if current_status.get("state") != "percentage_rollout":
            start_percentage = min(step_size, target_percentage)
        else:
            start_percentage = min(current_percentage + step_size, target_percentage)
        
        success = flag_manager.set_percentage_rollout(flag_name, start_percentage)
        
        if not success:
            raise HTTPException(status_code=500, detail=f"Failed to setup gradual rollout")
        
        return {
            "flag_name": flag_name,
            "current_percentage": start_percentage,
            "target_percentage": target_percentage,
            "step_size": step_size,
            "next_step_percentage": min(start_percentage + step_size, target_percentage),
            "rollout_complete": start_percentage >= target_percentage,
            "message": f"Gradual rollout started at {start_percentage}%"
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to setup gradual rollout for '{flag_name}': {str(e)}")
        raise HTTPException(status_code=500, detail=f"Failed to setup gradual rollout: {str(e)}")


@router.post("/rollback/{flag_name}")
async def rollback_feature(flag_name: str):
    """Rollback a feature flag (disable it)."""
    try:
        flag_manager = get_feature_flag_manager()
        
        if not flag_manager.get_flag_status(flag_name):
            raise HTTPException(status_code=404, detail=f"Feature flag '{flag_name}' not found")
        
        success = flag_manager.disable_flag(flag_name)
        
        if not success:
            raise HTTPException(status_code=500, detail=f"Failed to rollback feature")
        
        updated_status = flag_manager.get_flag_status(flag_name)
        
        return {
            "flag_name": flag_name,
            "status": "rolled_back",
            "updated_flag": FeatureFlagStatus(**updated_status),
            "message": f"Feature '{flag_name}' has been rolled back (disabled)"
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to rollback feature '{flag_name}': {str(e)}")
        raise HTTPException(status_code=500, detail=f"Failed to rollback feature: {str(e)}")


@router.get("/health")
async def feature_flags_health():
    """Health check endpoint for feature flags system."""
    try:
        flag_manager = get_feature_flag_manager()
        all_flags = flag_manager.get_all_flags_status()
        
        # Count flags by state
        state_counts = {}
        for flag_data in all_flags.values():
            if flag_data:
                state = flag_data.get("state", "unknown")
                state_counts[state] = state_counts.get(state, 0) + 1
        
        # Check client factory health
        client_factory = get_client_factory()
        client_stats = client_factory.get_client_stats()
        
        return {
            "status": "healthy",
            "total_flags": len(all_flags),
            "flags_by_state": state_counts,
            "client_factory_status": {
                "langchain_client_ready": client_stats.get("langchain_client_created", False),
                "gemini_client_ready": client_stats.get("gemini_client_created", False)
            }
        }
        
    except Exception as e:
        logger.error(f"Feature flags health check failed: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Health check failed: {str(e)}")