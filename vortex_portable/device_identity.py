"""OpenClaw device identity management - persistent Ed25519 keypair storage."""

import json
import os
from pathlib import Path
from typing import Dict, Any, Optional
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey
from cryptography.hazmat.primitives import serialization
import base64


class DeviceIdentity:
    """Manages persistent Ed25519 device identity for OpenClaw."""
    
    def __init__(self, device_id: str, storage_path: Optional[str] = None):
        """
        Initialize device identity manager.
        
        Args:
            device_id: Unique device identifier
            storage_path: Path to store device keypair (default: .openclaw-device.json in cwd)
        """
        self.device_id = device_id
        self.storage_path = Path(storage_path) if storage_path else Path(".openclaw-device.json")
        self._private_key: Optional[Ed25519PrivateKey] = None
        self._public_key_b64: Optional[str] = None
        
    def _load_or_generate_keypair(self) -> None:
        """Load existing keypair from storage or generate a new one."""
        if self.storage_path.exists():
            # Load existing keypair
            with open(self.storage_path, 'r') as f:
                data = json.load(f)
                
            # Verify device ID matches
            if data.get("deviceId") != self.device_id:
                raise ValueError(
                    f"Device identity file exists for different device: {data.get('deviceId')} "
                    f"(expected: {self.device_id})"
                )
            
            # Load private key from base64
            private_key_b64 = data.get("privateKey")
            if not private_key_b64:
                raise ValueError("Device identity file missing privateKey")
                
            private_key_bytes = base64.b64decode(private_key_b64)
            self._private_key = Ed25519PrivateKey.from_private_bytes(private_key_bytes)
            
            # Reconstruct public key
            public_key = self._private_key.public_key()
            public_key_bytes = public_key.public_bytes(
                encoding=serialization.Encoding.Raw,
                format=serialization.PublicFormat.Raw
            )
            # OpenClaw uses URL-safe base64 for public keys
            self._public_key_b64 = base64.urlsafe_b64encode(public_key_bytes).decode('ascii').rstrip('=')
            
        else:
            # Generate new keypair
            self._private_key = Ed25519PrivateKey.generate()
            public_key = self._private_key.public_key()
            
            # Get public key as URL-safe base64
            public_key_bytes = public_key.public_bytes(
                encoding=serialization.Encoding.Raw,
                format=serialization.PublicFormat.Raw
            )
            self._public_key_b64 = base64.urlsafe_b64encode(public_key_bytes).decode('ascii').rstrip('=')
            
            # Get private key bytes for storage
            private_key_bytes = self._private_key.private_bytes(
                encoding=serialization.Encoding.Raw,
                format=serialization.PrivateFormat.Raw,
                encryption_algorithm=serialization.NoEncryption()
            )
            
            # Save to storage
            data = {
                "deviceId": self.device_id,
                "publicKey": self._public_key_b64,
                "privateKey": base64.b64encode(private_key_bytes).decode('ascii'),
                "note": "OpenClaw device identity - keep this file secure!"
            }
            
            with open(self.storage_path, 'w') as f:
                json.dump(data, f, indent=2)
            
            # Set restrictive permissions (owner read/write only)
            if hasattr(os, 'chmod'):
                os.chmod(self.storage_path, 0o600)
    
    def get_device_identity(self, signed_at_ms: int, challenge_nonce: Optional[str] = None) -> Dict[str, Any]:
        """
        Generate device identity for OpenClaw connect request.
        
        Args:
            signed_at_ms: Current timestamp in milliseconds
            challenge_nonce: Optional challenge nonce from gateway
            
        Returns:
            Device identity dict with id, publicKey, signature, signedAt
        """
        if self._private_key is None:
            self._load_or_generate_keypair()
        
        # Sign the device identity (OpenClaw challenge-response protocol)
        # If nonce present: sign the nonce (proves we have the private key now)
        # If no nonce: sign the device ID (proves ownership)
        if challenge_nonce:
            signature_data = challenge_nonce.encode()
        else:
            signature_data = self.device_id.encode()
        
        signature_bytes = self._private_key.sign(signature_data)
        
        signature_bytes = self._private_key.sign(signature_data)
        # OpenClaw uses URL-safe base64 for signatures (no padding)
        signature_b64 = base64.urlsafe_b64encode(signature_bytes).decode('ascii').rstrip('=')
        
        device = {
            "id": self.device_id,
            "publicKey": self._public_key_b64,
            "signedAt": signed_at_ms,
            "signature": signature_b64,
        }
        
        if challenge_nonce:
            device["nonce"] = challenge_nonce
            
        return device
    
    def get_public_key_b64(self) -> str:
        """Get the device's public key as URL-safe base64 string."""
        if self._public_key_b64 is None:
            self._load_or_generate_keypair()
        return self._public_key_b64
