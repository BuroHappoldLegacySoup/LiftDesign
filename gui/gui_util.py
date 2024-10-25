from PyQt5.QtWidgets import QTableWidget, QWidget, QCheckBox, QLineEdit, QComboBox

class GuiUtility:
    @staticmethod
    def populate_table_from_input(table: QTableWidget, data_list: list, description_column: int = 0, start_column: int = 1):
        """
        Populate a QTableWidget with data from a list of dictionaries.
        
        Args:
            table (QTableWidget): The table widget to populate
            data_list (list): List of dictionaries containing the data to populate
            description_column (int): Column index containing descriptions (default 0)
            start_column (int): Starting column index for data population (default 1)
        """
        if not data_list:
            return

        for col, system_data in enumerate(data_list, start=start_column):
            for row in range(table.rowCount()):
                description = table.item(row, description_column).text()
                if description not in system_data:
                    continue
                    
                cell_widget = table.cellWidget(row, col)
                value = system_data[description]
                
                GuiUtility._populate_widget(cell_widget, value)
    
    @staticmethod
    def _populate_widget(widget, value):
        """
        Populate a specific widget with a value based on its type.
        
        Args:
            widget: The widget to populate (QLineEdit, QComboBox, or QWidget containing QCheckBox)
            value: The value to set in the widget
        """
        if not widget:
            return
            
        # Handle QWidget containing QCheckBox
        if isinstance(widget, QWidget) and not isinstance(widget, (QLineEdit, QComboBox)):
            checkbox = GuiUtility._get_checkbox_from_widget(widget)
            if checkbox:
                checkbox.setChecked(bool(value))
        
        # Handle QLineEdit
        elif isinstance(widget, QLineEdit):
            widget.setText(str(value))
        
        # Handle QComboBox
        elif isinstance(widget, QComboBox):
            index = widget.findText(str(value))
            if index >= 0:
                widget.setCurrentIndex(index)
    
    @staticmethod
    def _get_checkbox_from_widget(widget):
        """
        Get the QCheckBox from a widget that might contain one in its layout.
        
        Args:
            widget (QWidget): The widget that might contain a QCheckBox
        
        Returns:
            QCheckBox or None: The found checkbox or None if not found
        """
        if isinstance(widget, QWidget):
            for child in widget.children():
                if isinstance(child, QCheckBox):
                    return child
        return None
    
    @staticmethod
    def collect_table_data(table: QTableWidget, description_column: int = 0, start_column: int = 1) -> list:
        """
        Collect data from a QTableWidget into a list of dictionaries.
        
        Args:
            table (QTableWidget): The table to collect data from
            description_column (int): Column index containing descriptions (default 0)
            start_column (int): Starting column index for data collection (default 1)
            
        Returns:
            list: List of dictionaries containing the collected data
        """
        systems_data = []
        
        for col in range(start_column, table.columnCount()):
            system_data = {}
            for row in range(table.rowCount()):
                description = table.item(row, description_column).text()
                cell_widget = table.cellWidget(row, col)
                
                value = GuiUtility._get_widget_value(cell_widget)
                if value is not None:
                    system_data[description] = value
                    
            systems_data.append(system_data)
            
        return systems_data
    
    @staticmethod
    def _get_widget_value(widget):
        """
        Get the value from a widget based on its type.
        
        Args:
            widget: The widget to get the value from
            
        Returns:
            The value from the widget, or None if the widget type is not supported
        """
        if not widget:
            return None
            
        # Handle QWidget containing QCheckBox
        if isinstance(widget, QWidget) and not isinstance(widget, (QLineEdit, QComboBox)):
            checkbox = GuiUtility._get_checkbox_from_widget(widget)
            if checkbox:
                return checkbox.isChecked()
        
        # Handle QLineEdit
        elif isinstance(widget, QLineEdit):
            return widget.text()
        
        # Handle QComboBox
        elif isinstance(widget, QComboBox):
            return widget.currentText()
            
        return None