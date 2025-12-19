"""
chatbot_health.py - Standalone Health Check Module

This module provides health check functionality for the ScheduleChatbot.
It can be used independently or integrated with other systems.

Usage:
    from chatbot_health import get_chatbot_health, register_health_routes
    
    # Standalone usage
    health = get_chatbot_health(chatbot)
    
    # Flask integration
    register_health_routes(app, chatbot)
"""

from datetime import datetime
from flask import jsonify
import logging


def get_chatbot_health(chatbot):
    """
    Get comprehensive health status of a chatbot instance.
    
    Args:
        chatbot: ScheduleChatbot instance
        
    Returns:
        dict: Health status report
    """
    if not chatbot:
        return {
            'overall_status': 'error',
            'error': 'Chatbot not initialized',
            'timestamp': datetime.now().isoformat()
        }
    
    try:
        # Call the chatbot's internal health check
        return chatbot.health_check()
    except Exception as e:
        return {
            'overall_status': 'error',
            'error': str(e),
            'timestamp': datetime.now().isoformat()
        }


def register_health_routes(app, chatbot, logger=None):
    """
    Register health check routes with a Flask app.
    
    This function adds two endpoints to your Flask app:
    - /api/chatbot-health: Comprehensive health check
    - /api/chatbot-status: Quick status check
    
    Args:
        app: Flask app instance
        chatbot: ScheduleChatbot instance
        logger: Optional logger instance
    """
    if not logger:
        logger = logging.getLogger(__name__)
    
    @app.route('/api/chatbot-health')
    def chatbot_health():
        """Comprehensive health check endpoint."""
        try:
            health = get_chatbot_health(chatbot)
            
            # Log health summary
            overall = health.get('overall_status', 'unknown')
            logger.info(f"🏥 Chatbot Health: {overall.upper()}")
            for check_name, check_data in health.get('checks', {}).items():
                status_symbol = "✅" if check_data.get('status') == 'ok' else "⚠️ " if check_data.get('status') == 'warning' else "❌"
                logger.debug(f"  {status_symbol} {check_name}: {check_data.get('message', 'N/A')}")
            
            return jsonify(health), 200
            
        except Exception as e:
            logger.error(f"❌ Error in health check: {e}", exc_info=True)
            return jsonify({
                'overall_status': 'error',
                'error': str(e),
                'timestamp': datetime.now().isoformat()
            }), 500
    
    @app.route('/api/chatbot-quick-status')
    def chatbot_quick_status():
        """Quick status check endpoint (faster than full health check)."""
        try:
            if not chatbot:
                return jsonify({
                    'available': False,
                    'error': 'Chatbot not initialized'
                }), 500
            
            data_loaded = chatbot.df is not None and len(chatbot.df) > 0
            
            status = {
                'available': data_loaded,
                'records': len(chatbot.df) if data_loaded else 0,
                'data_state': 'ready' if chatbot.data_loaded else 'waiting',
                'timestamp': datetime.now().isoformat()
            }
            
            return jsonify(status), 200
            
        except Exception as e:
            logger.error(f"❌ Error in quick status: {e}")
            return jsonify({
                'available': False,
                'error': str(e)
            }), 500
    
    logger.info("✅ Health check routes registered: /api/chatbot-health, /api/chatbot-quick-status")
