#!/usr/bin/env python3
"""
Database backup script for Student Database v2.0

This script provides command-line interface for backing up and restoring
the student database. It can be run manually or scheduled via cron.

Usage:
    python scripts/backup.py create --type full
    python scripts/backup.py create --type incremental --since 2024-01-01
    python scripts/backup.py restore --file backup_20240101_120000.json.gz
    python scripts/backup.py list
    python scripts/backup.py cleanup --keep-days 30
"""

import os
import sys
import argparse
from datetime import datetime, date, timedelta
from pathlib import Path

# Add the parent directory to sys.path so we can import from the main app
sys.path.insert(0, str(Path(__file__).parent.parent))

from app import create_app
from utils.backup import DatabaseBackup
import logging

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('backup.log'),
        logging.StreamHandler(sys.stdout)
    ]
)

logger = logging.getLogger(__name__)

def create_backup(backup_type: str, since_date: str = None, compress: bool = True, include_logs: bool = True):
    """Create a database backup."""
    try:
        app = create_app()
        
        with app.app_context():
            backup_manager = DatabaseBackup()
            
            if backup_type == 'full':
                logger.info("Creating full backup...")
                result = backup_manager.create_full_backup(
                    compress=compress,
                    include_logs=include_logs
                )
            elif backup_type == 'incremental':
                if not since_date:
                    # Default to last 7 days
                    since_date = (date.today() - timedelta(days=7)).isoformat()
                
                since_date_obj = datetime.strptime(since_date, '%Y-%m-%d').date()
                logger.info(f"Creating incremental backup since {since_date}...")
                result = backup_manager.create_incremental_backup(
                    since_date=since_date_obj,
                    compress=compress
                )
            else:
                raise ValueError(f"Unknown backup type: {backup_type}")
            
            if result['status'] == 'success':
                info = result['backup_info']
                logger.info(f" Backup created successfully:")
                logger.info(f"  File: {info['file_path']}")
                logger.info(f"  Size: {info['file_size']:,} bytes")
                logger.info(f"  Records: {info['records_backed_up']:,}")
                return True
            else:
                logger.error(f" Backup failed: {result['error']}")
                return False
                
    except Exception as e:
        logger.error(f" Error creating backup: {e}")
        return False

def restore_backup(backup_file: str, restore_mode: str = 'replace'):
    """Restore database from backup."""
    try:
        app = create_app()
        
        with app.app_context():
            backup_manager = DatabaseBackup()
            
            # Verify backup first
            logger.info(f"Verifying backup integrity: {backup_file}")
            verify_result = backup_manager.verify_backup_integrity(backup_file)
            
            if verify_result['status'] == 'error':
                logger.error(f" Backup verification failed: {verify_result['error']}")
                return False
            elif verify_result['status'] == 'warning':
                logger.warning(f"  Backup has issues but may still be restorable")
                for issue in verify_result['integrity_info'].get('consistency_issues', []):
                    logger.warning(f"  - {issue}")
                
                response = input("Continue with restore? (y/N): ")
                if response.lower() != 'y':
                    logger.info("Restore cancelled by user")
                    return False
            
            # Confirm restore operation
            if restore_mode == 'replace':
                logger.warning("  REPLACE mode will delete all existing data!")
                response = input("Are you sure you want to continue? Type 'YES' to confirm: ")
                if response != 'YES':
                    logger.info("Restore cancelled by user")
                    return False
            
            logger.info(f"Restoring backup: {backup_file} (mode: {restore_mode})")
            result = backup_manager.restore_backup(backup_file, restore_mode)
            
            if result['status'] == 'success':
                info = result['restore_info']
                logger.info(f" Restore completed successfully:")
                logger.info(f"  Mode: {info['restore_mode']}")
                logger.info(f"  Records restored: {info['total_restored']:,}")
                for table, count in info['restored_counts'].items():
                    if count > 0:
                        logger.info(f"    {table}: {count:,}")
                return True
            else:
                logger.error(f" Restore failed: {result['error']}")
                return False
                
    except Exception as e:
        logger.error(f" Error restoring backup: {e}")
        return False

def list_backups():
    """List all available backups."""
    try:
        backup_manager = DatabaseBackup()
        backups = backup_manager.list_backups()
        
        if not backups:
            logger.info("No backups found")
            return True
        
        logger.info(f"Found {len(backups)} backup(s):")
        logger.info("-" * 80)
        
        for backup in backups:
            logger.info(f"File: {backup['filename']}")
            logger.info(f"  Size: {backup['size_mb']} MB")
            logger.info(f"  Created: {backup['created']}")
            logger.info(f"  Type: {backup.get('backup_type', 'unknown')}")
            logger.info(f"  Records: {backup.get('total_records', 'unknown')}")
            logger.info(f"  Compressed: {'Yes' if backup['compressed'] else 'No'}")
            logger.info("-" * 40)
        
        total_size = sum(backup['size_mb'] for backup in backups)
        logger.info(f"Total backup storage: {total_size:.2f} MB")
        
        return True
        
    except Exception as e:
        logger.error(f" Error listing backups: {e}")
        return False

def cleanup_backups(keep_days: int = 30, keep_minimum: int = 5):
    """Clean up old backup files."""
    try:
        backup_manager = DatabaseBackup()
        
        logger.info(f"Cleaning up backups older than {keep_days} days (keeping minimum {keep_minimum})")
        result = backup_manager.cleanup_old_backups(keep_days, keep_minimum)
        
        if result['status'] == 'success':
            info = result['cleanup_info']
            logger.info(f" Cleanup completed:")
            logger.info(f"  Files deleted: {info['files_deleted']}")
            logger.info(f"  Space freed: {info['space_freed_mb']} MB")
            logger.info(f"  Files kept: {info['files_kept']}")
            
            if info['deleted_files']:
                logger.info("  Deleted files:")
                for file_info in info['deleted_files']:
                    logger.info(f"    - {file_info['filename']} ({file_info['size_mb']} MB)")
            
            return True
        else:
            logger.error(f" Cleanup failed: {result['error']}")
            return False
            
    except Exception as e:
        logger.error(f" Error cleaning up backups: {e}")
        return False

def verify_backup(backup_file: str):
    """Verify backup file integrity."""
    try:
        backup_manager = DatabaseBackup()
        
        logger.info(f"Verifying backup: {backup_file}")
        result = backup_manager.verify_backup_integrity(backup_file)
        
        if result['status'] == 'success':
            info = result['integrity_info']
            logger.info(f" Backup verification passed:")
            logger.info(f"  File: {info['file_path']}")
            logger.info(f"  Size: {info['file_size']:,} bytes")
            logger.info(f"  Type: {info['backup_type']}")
            logger.info(f"  Created: {info['created_at']}")
            logger.info(f"  Total records: {info['total_records']:,}")
            
            logger.info("  Record counts:")
            for table, count in info['data_counts'].items():
                logger.info(f"    {table}: {count:,}")
            
            return True
        elif result['status'] == 'warning':
            info = result['integrity_info']
            logger.warning(f"  Backup verification passed with warnings:")
            logger.warning(f"  Structure valid: {info['structure_valid']}")
            logger.warning(f"  Metadata complete: {info['metadata_complete']}")
            
            if info['consistency_issues']:
                logger.warning("  Consistency issues found:")
                for issue in info['consistency_issues']:
                    logger.warning(f"    - {issue}")
            
            return True
        else:
            logger.error(f" Backup verification failed: {result['error']}")
            return False
            
    except Exception as e:
        logger.error(f" Error verifying backup: {e}")
        return False

def main():
    """Main entry point for the backup script."""
    parser = argparse.ArgumentParser(
        description="Database backup and restore utility for Student Database v2.0",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Create full backup
  python scripts/backup.py create --type full
  
  # Create incremental backup for last 7 days
  python scripts/backup.py create --type incremental --since 2024-01-01
  
  # List all backups
  python scripts/backup.py list
  
  # Restore from backup (replace mode)
  python scripts/backup.py restore --file backup_20240101_120000.json.gz --mode replace
  
  # Clean up old backups
  python scripts/backup.py cleanup --keep-days 30 --keep-minimum 5
  
  # Verify backup integrity
  python scripts/backup.py verify --file backup_20240101_120000.json.gz
        """
    )
    
    subparsers = parser.add_subparsers(dest='command', help='Available commands')
    
    # Create backup command
    create_parser = subparsers.add_parser('create', help='Create a backup')
    create_parser.add_argument('--type', choices=['full', 'incremental'], required=True,
                              help='Type of backup to create')
    create_parser.add_argument('--since', type=str,
                              help='For incremental backups, date to backup since (YYYY-MM-DD)')
    create_parser.add_argument('--no-compress', action='store_true',
                              help='Disable compression')
    create_parser.add_argument('--no-logs', action='store_true',
                              help='Exclude trial logs from backup')
    
    # Restore backup command
    restore_parser = subparsers.add_parser('restore', help='Restore from backup')
    restore_parser.add_argument('--file', required=True,
                               help='Backup file to restore from')
    restore_parser.add_argument('--mode', choices=['replace', 'skip'], default='replace',
                               help='Restore mode (replace existing data or skip duplicates)')
    
    # List backups command
    list_parser = subparsers.add_parser('list', help='List available backups')
    
    # Cleanup command
    cleanup_parser = subparsers.add_parser('cleanup', help='Clean up old backups')
    cleanup_parser.add_argument('--keep-days', type=int, default=30,
                               help='Number of days to keep backups (default: 30)')
    cleanup_parser.add_argument('--keep-minimum', type=int, default=5,
                               help='Minimum number of backups to keep (default: 5)')
    
    # Verify command
    verify_parser = subparsers.add_parser('verify', help='Verify backup integrity')
    verify_parser.add_argument('--file', required=True,
                              help='Backup file to verify')
    
    args = parser.parse_args()
    
    if not args.command:
        parser.print_help()
        return False
    
    # Execute the requested command
    success = False
    
    if args.command == 'create':
        success = create_backup(
            backup_type=args.type,
            since_date=args.since,
            compress=not args.no_compress,
            include_logs=not args.no_logs
        )
    
    elif args.command == 'restore':
        success = restore_backup(
            backup_file=args.file,
            restore_mode=args.mode
        )
    
    elif args.command == 'list':
        success = list_backups()
    
    elif args.command == 'cleanup':
        success = cleanup_backups(
            keep_days=args.keep_days,
            keep_minimum=args.keep_minimum
        )
    
    elif args.command == 'verify':
        success = verify_backup(args.file)
    
    return success

if __name__ == '__main__':
    success = main()
    sys.exit(0 if success else 1)