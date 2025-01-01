classdef UTM_exported < matlab.apps.AppBase

    % Properties that correspond to app components
    properties (Access = public)
        UIFigure                        matlab.ui.Figure
        Label_3                         matlab.ui.control.Label
        SpeedLabel                      matlab.ui.control.Label
        SaveDataButton                  matlab.ui.control.Button
        StatusBox                       matlab.ui.control.TextArea
        Label                           matlab.ui.control.Label
        DirectionKnob                   matlab.ui.control.DiscreteKnob
        DirectionKnobLabel              matlab.ui.control.Label
        TareLocationButton              matlab.ui.control.Button
        StatusLamp                      matlab.ui.control.Lamp
        Label_2                         matlab.ui.control.Label
        EmergencySTOPButton             matlab.ui.control.Button
        MotorsSwitch                    matlab.ui.control.RockerSwitch
        MotorsSwitchLabel               matlab.ui.control.Label
        SetRPMEditField                 matlab.ui.control.NumericEditField
        SetRPMEditFieldLabel            matlab.ui.control.Label
        RPMSwitch                       matlab.ui.control.Switch
        RPMGauge                        matlab.ui.control.Gauge
        SwitchLabel                     matlab.ui.control.Label
        VelocitySwitch                  matlab.ui.control.Switch
        VelocitySwitchLabel             matlab.ui.control.Label
        PositionSwitch                  matlab.ui.control.Switch
        PositionSwitchLabel             matlab.ui.control.Label
        LoadCellSwitch                  matlab.ui.control.Switch
        LoadCellSwitchLabel             matlab.ui.control.Label
        deltaGauge                      matlab.ui.control.LinearGauge
        delta0000mmLabel                matlab.ui.control.Label
        setRPMKnob                      matlab.ui.control.Knob
        KnobLabel                       matlab.ui.control.Label
        ConnectionSwitch                matlab.ui.control.Switch
        ConnectionSwitchLabel           matlab.ui.control.Label
        AvailableCOMportsDropDown       matlab.ui.control.DropDown
        AvailableCOMportsDropDownLabel  matlab.ui.control.Label
        ScanforCOMportsButton           matlab.ui.control.Button
        TabGroup                        matlab.ui.container.TabGroup
        StressStrainTab                 matlab.ui.container.Tab
        mmLabel                         matlab.ui.control.Label
        AreaEditField                   matlab.ui.control.NumericEditField
        AreaEditFieldLabel              matlab.ui.control.Label
        CropButton                      matlab.ui.control.Button
        ShowrangeSlider                 matlab.ui.control.RangeSlider
        ShowrangeSliderLabel            matlab.ui.control.Label
        ClearplotButton                 matlab.ui.control.Button
        ImagePlot                       matlab.ui.control.UIAxes
        CurvePlot                       matlab.ui.control.UIAxes
        ConsoleTab                      matlab.ui.container.Tab
        BaudRateDropDown                matlab.ui.control.DropDown
        BaudRateDropDownLabel           matlab.ui.control.Label
        CommandEditField                matlab.ui.control.EditField
        CommandEditFieldLabel           matlab.ui.control.Label
        ClearConsoleButton              matlab.ui.control.Button
        TimeStampButton                 matlab.ui.control.StateButton
        AutoscrollButton                matlab.ui.control.StateButton
        LineEndingDropDown              matlab.ui.control.DropDown
        SendButton                      matlab.ui.control.Button
        ConsoleTextArea                 matlab.ui.control.TextArea
        ConsoleTextAreaLabel            matlab.ui.control.Label
        LoadPlotTab                     matlab.ui.container.Tab
        MarkersCheckBox                 matlab.ui.control.CheckBox
        CalibrationPanel                matlab.ui.container.Panel
        ScaleEditField                  matlab.ui.control.NumericEditField
        ScaleEditFieldLabel             matlab.ui.control.Label
        OffsetEditField                 matlab.ui.control.NumericEditField
        OffsetEditFieldLabel            matlab.ui.control.Label
        CalibrateButton                 matlab.ui.control.Button
        WeightinKgEditField             matlab.ui.control.NumericEditField
        WeightinKgEditFieldLabel        matlab.ui.control.Label
        CropLoadButton                  matlab.ui.control.Button
        CropLoadSlider                  matlab.ui.control.RangeSlider
        ClearLoadPlotButton             matlab.ui.control.Button
        TareButton                      matlab.ui.control.Button
        LoadPlot                        matlab.ui.control.UIAxes
    end

    
    properties (Access = public)
        consoleText % Description
        device % Description
        data
        hExternalFigure
        hExternalPlot
        dataCounter = 0;
        maxDataCount = 500;
        hLoadPlot % Description
        hStressPlot
        maxConsoleLines = 500;
        connectionEstablished = 0;
        previousConnectionState = 0;
        positionRaw = 0
        position = 0
        position0 = 0;
        Timer1
        Timer2
        hLimitPlots
    end
    
    methods (Access = public)
        
        function AppendToConsole(app, line)
            if isempty(app.ConsoleTextArea.Value{1})
                app.ConsoleTextArea.Value{1} = convertStringsToChars(line);
            else
                app.ConsoleTextArea.Value{end+1} = convertStringsToChars(line);
            end
            

            if app.AutoscrollButton.Value
                scroll(app.ConsoleTextArea,"bottom");
            end
        end

        function ScanForCOMPorts(app)
            ports = serialportlist;
            nPorts = length(ports);
            if nPorts == 0
                msg = "No COM ports detected on system! Please check the USB cable.";
                app.AppendToConsole(msg);
                app.TabGroup.SelectedTab = app.ConsoleTab;
                msgbox(msg,"Error","error")
            end
            for iPort = 1:nPorts
                port = ports(iPort);
                app.AvailableCOMportsDropDown.Items{iPort} = convertStringsToChars(port);
                app.AppendToConsole(['Found port: ', convertStringsToChars(port)]);
            end
        end

        function GetSerialData(app, src, ~)
            
            raw = fgets(src);
            raw = strtrim(raw);
            
            timestamp = datetime('now','TimeZone','local','Format','HH:mm:ss.SSS');
            line = [];
            if app.TimeStampButton.Value
                time = datestr(timestamp,'HH:MM:SS.FFF');
                line = [line, time, ' -> '];
            end
            line = [line, raw];
            
            
            if contains(line, 'Welcome')
                app.connectionEstablished = 1;
                return
            end
            
            if contains(line, 'Velocity: ')
                str = extractAfter(line, 'Velocity: ');
                strArray = strsplit(str, '\t');
                val = str2double(strArray);
                vel = val(2);
                
                if strcmpi(app.RPMSwitch.Value, "RPM")
                    app.RPMGauge.Value = vel;
                    app.SpeedLabel.Text = sprintf("Speed: %0.0f RPM",vel);
                else
                    vx = vel/60/20*5;
                    app.RPMGauge.Value = vx;
                    app.SpeedLabel.Text = sprintf("Speed: %0.2f mm/s", vx);
                end
                return
            end

            if contains(line, 'Total Angle: ')
                str = extractAfter(line, 'Total Angle: ');
                strArray = strsplit(str, '\t');
                val = str2double(strArray);
                pos = val*360/4096; % degrees
                pos = pos/360;   % rounds
                pos = pos/20;    % rounds on screw
                pos = pos*5;      % mm
                
                app.positionRaw = pos;

                app.position = app.positionRaw - app.position0;

                app.delta0000mmLabel.Text = ['$\delta=', sprintf('%0.4f',app.position), '$ mm'];
                app.delta0000mmLabel.Interpreter = "latex";
                app.deltaGauge.Value = app.position;

                return
            end
            
            if contains(line, 'Command')
                return
            end

            app.AppendToConsole(line);

            if length(app.ConsoleTextArea.Value) >= app.maxConsoleLines
                app.ClearConsoleButtonPushed()
            end
            
            strArray = strsplit(line, '\t');
            force = str2double(strArray);
            app.ProcessLoadData(force);

            
        end

        function ProcessLoadData(app, force)
            
            if isempty(force); return; end
            % force
            
            app.dataCounter = app.dataCounter+1;
            
            timestamp = datetime('now','TimeZone','local','Format','HH:mm:ss.SSS');
            app.data{app.dataCounter, 1} = timestamp;
            app.data{app.dataCounter, 2} = force;
            
            y = [app.data{:,2}];
            x = [app.data{:,1}];

            windowDuration = 1;
            samplingRate = 10;
            windowSize = round(windowDuration * samplingRate);
            ym = movmean(y, windowSize);
            set(app.hLoadPlot,'XData',x,'YData',ym);
            if length(app.data) >= app.maxDataCount
                xlim(app.LoadPlot, 'auto');
            end
        end
        
        function RescaleTime(app)
            freq = 10;
            timeOffset = app.maxDataCount / freq
            currentTime = datetime('now','TimeZone','local','Format','HH:mm:ss.SSS');
            futureTime = currentTime + seconds(timeOffset)
            xlim(app.LoadPlot, [currentTime, futureTime]);
        end

        function RedrawLoadPlot(app)
            delete(app.hLoadPlot)
            currentTime = datetime('now','TimeZone','local','Format','HH:mm:ss.SSS');
            app.hLoadPlot = plot(app.LoadPlot, currentTime, NaN, '-b.');
            app.RescaleTime();
        end

        function ClearLoadData(app)
            app.data = {};
            app.dataCounter = 0;
        end
        
        function Timer2CallbackFcn(app, ~, ~)
            try
                if strcmpi(app.PositionSwitch.Value, 'On')
                    app.device.writeline("GetTotalAngle");
                end
                if strcmpi(app.VelocitySwitch.Value, 'On')
                    app.device.writeline("GetVelocity");
                end
            end
        end

        function Timer1CallbackFcn(app, ~, ~)
            % Checking connection every 0.5 seconds.
            if isobject(app.device) && isvalid(app.device)
                try getpinstatus(app.device); 
                catch
                    app.connectionEstablished = 0;
                end
            else
                app.connectionEstablished = 0;
            end
            
            if app.connectionEstablished == app.previousConnectionState; return; end
            % Ensures that this below only gets run ONCE!
            app.previousConnectionState = app.connectionEstablished;
            
            if app.connectionEstablished
                app.OnSerialConnected();
            else
                app.OnSerialDisconnected();
            end
        end

        function OnSerialConnected(app)
            app.StatusBox.Value = "Status: Connected to UTM.";
            app.StatusLamp.Color = 'g';
            app.StatusLamp.Tooltip = "Connected to UTM";
            disp("Connected to UTM")
            app.LoadCellSwitch.Enable = "On";
            app.PositionSwitch.Enable = "On";
            app.VelocitySwitch.Enable = "On";
            app.MotorsSwitch.Enable = "On";
            app.RPMSwitch.Enable = "On";
            app.SetRPMEditField.Enable = "On";
            app.setRPMKnob.Enable = "On";
            app.DirectionKnob.Enable = "On";
            app.BaudRateDropDown.Enable = "Off";
            app.LineEndingDropDown.Enable = "Off";
            app.AvailableCOMportsDropDown.Enable = "Off";
            app.EmergencySTOPButton.Enable = "On";
            app.RPMGauge.Enable = "On";
            app.deltaGauge.Enable = "On";
            app.TareLocationButton.Enable = "On";

            app.MotorsSwitch.Value = "Off";
            app.setRPMKnob.Value = 0;
            app.SetRPMEditField.Value = 0;
            app.DirectionKnob.Value = "Stop";
            
            % This helps with getting weird noisy velocities
            app.device.writeline("Enable");
            pause(0.1);
            app.device.writeline("Disable");
        end

        function OnSerialDisconnected(app)
            app.StatusBox.Value = "Status: Not connected to UTM.";
            app.StatusLamp.Color = 'k';
            app.StatusLamp.Tooltip = "Not connected to UTM";
            disp("Disconnected from UTM")
            app.LoadCellSwitch.Enable = "Off";
            app.PositionSwitch.Enable = "Off";
            app.VelocitySwitch.Enable = "Off";
            app.MotorsSwitch.Enable = "Off";
            app.RPMSwitch.Enable = "Off";
            app.SetRPMEditField.Enable = "Off";
            app.setRPMKnob.Enable = "Off";
            app.DirectionKnob.Enable = "Off";
            app.BaudRateDropDown.Enable = "On";
            app.LineEndingDropDown.Enable = "On";
            app.AvailableCOMportsDropDown.Enable = "On";
            app.EmergencySTOPButton.Enable = "Off";
            app.RPMGauge.Enable = "Off";
            app.deltaGauge.Enable = "Off";
            app.TareLocationButton.Enable = "Off";

            app.MotorsSwitch.Value = "Off";
            app.setRPMKnob.Value = 0;
            app.SetRPMEditField.Value = 0;
            app.DirectionKnob.Value = "Stop";
        end
    end
    

    % Callbacks that handle component events
    methods (Access = private)

        % Code that executes after component creation
        function startupFcn(app)
            clc
            app.ScanForCOMPorts();
            app.data = {};
            
            app.Timer1 = timer;
            app.Timer1.Period = 0.5;
            app.Timer1.ExecutionMode = 'fixedRate';
            app.Timer1.TimerFcn = @(~,~)app.Timer1CallbackFcn();
            start(app.Timer1);

            app.Timer2 = timer;
            app.Timer2.Period = 1;
            app.Timer2.ExecutionMode = 'fixedRate';
            app.Timer2.TimerFcn = @(~,~)app.Timer2CallbackFcn();
            start(app.Timer2);
            
            currentTime = datetime('now','TimeZone','local','Format','HH:mm:ss.SSS');
            app.hLoadPlot = plot(app.LoadPlot, currentTime, NaN, '-b.');
            hold(app.LoadPlot,'On');
            app.hLimitPlots = plot(app.LoadPlot,currentTime, NaN);

            app.OnSerialDisconnected();
            

        end

        % Button pushed function: ScanforCOMportsButton
        function ScanforCOMportsButtonPushed(app, event)
            app.ScanForCOMPorts();
            app.data = {};
        end

        % Button pushed function: ClearConsoleButton
        function ClearConsoleButtonPushed(app, event)
            app.ConsoleTextArea.Value = {''};
        end

        % Value changed function: ConnectionSwitch
        function ConnectionSwitchValueChanged(app, event)
            value = app.ConnectionSwitch.Value;
            app.TabGroup.SelectedTab = app.ConsoleTab;
            if strcmpi(value, 'on')
                app.AppendToConsole(['Connecting on COM port: ', convertStringsToChars(app.AvailableCOMportsDropDown.Value)])
                port = app.AvailableCOMportsDropDown.Value;
                baudRate = str2double(app.BaudRateDropDown.Value);
                
                try app.device = serialport(port, baudRate,"Timeout",5);
                catch
                    app.AppendToConsole('Cannot connect to port, verify that port exists and is open!')
                    return
                end
                switch app.LineEndingDropDown.Value
                    case "New Line"
                        terminator = 'LF';
                    case "Carriage Return"
                        terminator = 'CR';
                    case "Both NL & CR"
                        terminator = 'CR/LF';
                end
                app.device.configureTerminator(terminator);
                app.device.configureCallback("terminator", @app.GetSerialData);
                
                

            else
                try 
                    app.device.delete();
                    app.AppendToConsole('Connection closed');
                end
                app.connectionEstablished = 0;
                app.OnSerialDisconnected();
            end
        end

        % Value changed function: MotorsSwitch
        function MotorsSwitchValueChanged(app, event)
            value = app.MotorsSwitch.Value;
            if strcmpi(value, 'on')
                app.device.writeline("Enable");
            else
                app.device.writeline("Disable");
            end
        end

        % Value changed function: CommandEditField
        function CommandEditFieldValueChanged(app, event)
            value = app.CommandEditField.Value;
            if ~isempty(value)
                app.device.writeline(value);
            end
        end

        % Close request function: UIFigure
        function UIFigureCloseRequest(app, event)
            
            selection = uiconfirm(app.UIFigure, ...
                'Are you sure you want to close the app?', ...
                'Close Confirmation', ...
                'Options', {'Yes', 'No'}, ...
                'DefaultOption', 'No', ...
                'Icon', 'warning');
            if strcmp(selection, 'No'); return; end

            try app.device.delete(); end
            try stop(app.Timer1); end
            try delete(app.Timer1); end
            try stop(app.Timer2); end
            try delete(app.Timer2); end
            disp('Goodbye')
            delete(app)
            
        end

        % Button pushed function: SendButton
        function SendButtonPushed(app, event)
            value = app.CommandEditField.Value;
            app.device.writeline(value);
        end

        % Button pushed function: EmergencySTOPButton
        function EmergencySTOPButtonPushed(app, event)
            app.device.writeline("EStop");
            app.DirectionKnob.Value = "Stop";
        end

        % Value changed function: setRPMKnob
        function setRPMKnobValueChanged(app, event)
            if strcmpi(app.RPMSwitch.Value, 'RPM')
                value = round(app.setRPMKnob.Value);
                app.SetRPMEditField.Value = value;
                rpmVal = value;
            else
                value = app.setRPMKnob.Value;
                app.SetRPMEditField.Value = value;
                rpmVal = round(value*60*20/5)
            end
            app.device.writeline(sprintf("SetSpeed %d", rpmVal*10));
        end

        % Value changed function: SetRPMEditField
        function SetRPMEditFieldValueChanged(app, event)
            if strcmpi(app.RPMSwitch.Value, 'RPM')
                value = round(app.SetRPMEditField.Value);
                app.SetRPMEditField.Value = value;
                app.setRPMKnob.Value = value;
                rpmVal = value;
            else
                value = app.SetRPMEditField.Value;
                rpmVal = value*60*20/5;
            end
            app.device.writeline(sprintf("SetSpeed %d", rpmVal*10));
        end

        % Value changed function: DirectionKnob
        function DirectionKnobValueChanged(app, event)
            value = app.DirectionKnob.Value;
            if strcmpi(value, 'Down')
                app.device.writeline("Backward");
            elseif strcmpi(value, 'Up')
                app.device.writeline("Forward");
            else 
                app.device.writeline("Stop");
            end
        end

        % Value changed function: RPMSwitch
        function RPMSwitchValueChanged(app, event)
            value = app.RPMSwitch.Value;            
            if strcmpi(value, 'RPM')
                val = app.SetRPMEditField.Value;
                val = val*60*20/5; %Convert to rpm
                
                app.setRPMKnob.Limits = [0, 240];
                app.setRPMKnob.MajorTicks = linspace(0, 240, 9);
                app.SetRPMEditField.Limits = [0, 240];
                
                app.SetRPMEditField.Value = val;
                app.setRPMKnob.Value = val;

                app.SetRPMEditFieldLabel.Text = "Set RPM:";
                app.RPMGauge.Limits = [-240, 240];
            else
                val = app.SetRPMEditField.Value;
                val = val/60/20*5; % Convert to mm/s
                
                app.setRPMKnob.Limits = [0, 1];
                app.setRPMKnob.MajorTicks = [0, 0.1, 0.2, 0.3, 0.4, 0.5, 0.6, 0.7, 0.8, 0.9, 1];
                app.SetRPMEditField.Limits = [0, 1];

                app.SetRPMEditField.Value = val;
                app.setRPMKnob.Value = val;

                app.SetRPMEditFieldLabel.Text = "Set mm/s:";
                app.RPMGauge.Limits = [-1, 1];
            end
            
        end

        % Value changed function: LoadCellSwitch
        function LoadCellSwitchValueChanged(app, event)
            value = app.LoadCellSwitch.Value;
            
            if strcmpi(value, 'On')
                app.device.writeline("LoadCellOn");
                % app.RedrawLoadPlot();
            else
                app.device.writeline("LoadCellOff");
                currentTime = datetime('now','TimeZone','local','Format','HH:mm:ss.SSS');
                app.dataCounter = app.dataCounter +1;
                app.data{app.dataCounter, 1} = currentTime;
                app.data{app.dataCounter, 2} = NaN;
                % app.RedrawLoadPlot();
            end
        end

        % Value changed function: PositionSwitch
        function PositionSwitchValueChanged(app, event)
            value = app.PositionSwitch.Value;
            % if strcmpi(value, 'On')
            %     app.device.writeline("AngleOn");
            % else
            %     app.device.writeline("AngleOff");
            % end
        end

        % Value changed function: VelocitySwitch
        function VelocitySwitchValueChanged(app, event)
            value = app.VelocitySwitch.Value;
            % if strcmpi(value, 'On')
            %     app.device.writeline("VelocityOn");
            % else
            %     app.device.writeline("VelocityOff");
            % end
        end

        % Button pushed function: ClearLoadPlotButton
        function ClearLoadPlotButtonPushed(app, event)
            app.ClearLoadData()
            % app.RedrawLoadPlot();
        end

        % Button pushed function: TareButton
        function TareButtonPushed(app, event)
            % app.device.Port
            
            
        end

        % Button pushed function: CalibrateButton
        function CalibrateButtonPushed(app, event)
            
        end

        % Button pushed function: CropLoadButton
        function CropLoadButtonPushed(app, event)
            % hFig = figure; hAx = gca();
            % hPlot = plot(hAx, app.hLoadPlot.XData, app.hLoadPlot.YData);
            x0 = app.CropLoadSlider.Value(1);
            x1 = app.CropLoadSlider.Value(2);

            np = length(app.hLoadPlot.XData);

            xlow = floor(x0/100 * np); if xlow == 0; xlow = 1; end
            xhigh = ceil(x1/100 * np);


            XD = app.hLoadPlot.XData();
            YD = app.hLoadPlot.YData();
            
            % app.data

            % num2cell(XD)
            
            app.data = [num2cell([XD(xlow:xhigh)])', num2cell([YD(xlow:xhigh)])'];
            

            [app.data{:,1}]
            set(app.hLoadPlot, 'XData', [app.data{:,1}],...
                               'YData', [app.data{:,2}])


            app.CropLoadSlider.Value = [0,100];

        end

        % Value changing function: CropLoadSlider
        function CropLoadSliderValueChanging(app, event)
            
            set(app.hLimitPlots, 'Visible', 'On')
            changingValue = event.Value;
            
            ymin = min(app.hLoadPlot.YData);
            ymax = max(app.hLoadPlot.YData);

            x0 = changingValue(1);
            x1 = changingValue(2);

            

            np = length(app.hLoadPlot.XData);

            xlow = floor(x0/100 * np); if xlow == 0; xlow = 1; end
            xhigh = ceil(x1/100 * np);
            
            XD = app.hLoadPlot.XData()';

            set(app.hLimitPlots, 'XData', [XD(xlow), XD(xlow), XD(xlow), XD(xhigh), XD(xhigh)],...
                                 'YData', [ymin, ymax, NaN, ymin, ymax],...
                                 'Color','k', 'linestyle','-');
        end

        % Value changed function: CropLoadSlider
        function CropLoadSliderValueChanged(app, event)
            value = app.CropLoadSlider.Value;
            set(app.hLimitPlots, 'Visible', 'Off')
        end

        % Button pushed function: SaveDataButton
        function SaveDataButtonPushed(app, event)
             
        end

        % Value changing function: setRPMKnob
        function setRPMKnobValueChanging(app, event)
            changingValue = event.Value;
            if strcmpi(app.RPMSwitch.Value, 'RPM')
                value = round(changingValue);
                app.SetRPMEditField.Value = value;
            else
                value = changingValue;
                % rpmVal = round(value*60*20/5)
                app.SetRPMEditField.Value = value;
                
            end
            % app.device.writeline(sprintf("SetSpeed %d", rpmVal*10));
        end

        % Button pushed function: TareLocationButton
        function TareLocationButtonPushed(app, event)
            app.position0 = app.positionRaw;
            % app.position0
        end

        % Value changed function: MarkersCheckBox
        function MarkersCheckBoxValueChanged(app, event)
            value = app.MarkersCheckBox.Value;
            if value
                app.hLoadPlot.Marker = '.';
            else
                app.hLoadPlot.Marker = 'none';
            end
        end
    end

    % Component initialization
    methods (Access = private)

        % Create UIFigure and components
        function createComponents(app)

            % Create UIFigure and hide until all components are created
            app.UIFigure = uifigure('Visible', 'off');
            app.UIFigure.Position = [100 100 1232 813];
            app.UIFigure.Name = 'MATLAB App';
            app.UIFigure.CloseRequestFcn = createCallbackFcn(app, @UIFigureCloseRequest, true);

            % Create TabGroup
            app.TabGroup = uitabgroup(app.UIFigure);
            app.TabGroup.Position = [2 184 699 630];

            % Create StressStrainTab
            app.StressStrainTab = uitab(app.TabGroup);
            app.StressStrainTab.Title = 'Stress/Strain';

            % Create CurvePlot
            app.CurvePlot = uiaxes(app.StressStrainTab);
            title(app.CurvePlot, 'Stress - strain curve')
            xlabel(app.CurvePlot, 'Strain [mm/mm]')
            ylabel(app.CurvePlot, 'Stress [N/mm^2]')
            zlabel(app.CurvePlot, 'Z')
            app.CurvePlot.Position = [22 266 419 330];

            % Create ImagePlot
            app.ImagePlot = uiaxes(app.StressStrainTab);
            title(app.ImagePlot, 'No blobs found in frame')
            app.ImagePlot.Position = [12 162 669 84];

            % Create ClearplotButton
            app.ClearplotButton = uibutton(app.StressStrainTab, 'push');
            app.ClearplotButton.Position = [452 563 100 23];
            app.ClearplotButton.Text = 'Clear plot';

            % Create ShowrangeSliderLabel
            app.ShowrangeSliderLabel = uilabel(app.StressStrainTab);
            app.ShowrangeSliderLabel.HorizontalAlignment = 'right';
            app.ShowrangeSliderLabel.Position = [458 534 69 22];
            app.ShowrangeSliderLabel.Text = 'Show range';

            % Create ShowrangeSlider
            app.ShowrangeSlider = uislider(app.StressStrainTab, 'range');
            app.ShowrangeSlider.Position = [459 523 219 3];

            % Create CropButton
            app.CropButton = uibutton(app.StressStrainTab, 'push');
            app.CropButton.Position = [452 463 100 23];
            app.CropButton.Text = 'Crop';

            % Create AreaEditFieldLabel
            app.AreaEditFieldLabel = uilabel(app.StressStrainTab);
            app.AreaEditFieldLabel.Position = [451 424 34 22];
            app.AreaEditFieldLabel.Text = 'Area:';

            % Create AreaEditField
            app.AreaEditField = uieditfield(app.StressStrainTab, 'numeric');
            app.AreaEditField.Limits = [0 1000];
            app.AreaEditField.HorizontalAlignment = 'left';
            app.AreaEditField.Position = [500 424 69 22];

            % Create mmLabel
            app.mmLabel = uilabel(app.StressStrainTab);
            app.mmLabel.Position = [571 424 25 22];
            app.mmLabel.Text = 'mm';

            % Create ConsoleTab
            app.ConsoleTab = uitab(app.TabGroup);
            app.ConsoleTab.Title = 'Console';

            % Create ConsoleTextAreaLabel
            app.ConsoleTextAreaLabel = uilabel(app.ConsoleTab);
            app.ConsoleTextAreaLabel.HorizontalAlignment = 'right';
            app.ConsoleTextAreaLabel.FontName = 'Consolas';
            app.ConsoleTextAreaLabel.Position = [323 574 51 22];
            app.ConsoleTextAreaLabel.Text = 'Console';

            % Create ConsoleTextArea
            app.ConsoleTextArea = uitextarea(app.ConsoleTab);
            app.ConsoleTextArea.FontName = 'Consolas';
            app.ConsoleTextArea.Position = [42 236 615 326];

            % Create SendButton
            app.SendButton = uibutton(app.ConsoleTab, 'push');
            app.SendButton.ButtonPushedFcn = createCallbackFcn(app, @SendButtonPushed, true);
            app.SendButton.Position = [488 201 65 23];
            app.SendButton.Text = 'Send';

            % Create LineEndingDropDown
            app.LineEndingDropDown = uidropdown(app.ConsoleTab);
            app.LineEndingDropDown.Items = {'New Line', 'Carriage Return', 'Both NL & CR'};
            app.LineEndingDropDown.Position = [252 164 100 22];
            app.LineEndingDropDown.Value = 'New Line';

            % Create AutoscrollButton
            app.AutoscrollButton = uibutton(app.ConsoleTab, 'state');
            app.AutoscrollButton.Text = 'Auto scroll';
            app.AutoscrollButton.Position = [382 164 66 23];
            app.AutoscrollButton.Value = true;

            % Create TimeStampButton
            app.TimeStampButton = uibutton(app.ConsoleTab, 'state');
            app.TimeStampButton.Text = 'Time Stamp';
            app.TimeStampButton.Position = [478 164 76 23];

            % Create ClearConsoleButton
            app.ClearConsoleButton = uibutton(app.ConsoleTab, 'push');
            app.ClearConsoleButton.ButtonPushedFcn = createCallbackFcn(app, @ClearConsoleButtonPushed, true);
            app.ClearConsoleButton.Position = [574 201 86 23];
            app.ClearConsoleButton.Text = 'Clear Console';

            % Create CommandEditFieldLabel
            app.CommandEditFieldLabel = uilabel(app.ConsoleTab);
            app.CommandEditFieldLabel.HorizontalAlignment = 'right';
            app.CommandEditFieldLabel.Position = [45 201 64 22];
            app.CommandEditFieldLabel.Text = 'Command:';

            % Create CommandEditField
            app.CommandEditField = uieditfield(app.ConsoleTab, 'text');
            app.CommandEditField.ValueChangedFcn = createCallbackFcn(app, @CommandEditFieldValueChanged, true);
            app.CommandEditField.Position = [124 201 353 22];

            % Create BaudRateDropDownLabel
            app.BaudRateDropDownLabel = uilabel(app.ConsoleTab);
            app.BaudRateDropDownLabel.HorizontalAlignment = 'right';
            app.BaudRateDropDownLabel.Position = [51 164 62 22];
            app.BaudRateDropDownLabel.Text = 'Baud Rate';

            % Create BaudRateDropDown
            app.BaudRateDropDown = uidropdown(app.ConsoleTab);
            app.BaudRateDropDown.Items = {'9600', '57600', '115200', '250000'};
            app.BaudRateDropDown.Position = [128 164 100 22];
            app.BaudRateDropDown.Value = '9600';

            % Create LoadPlotTab
            app.LoadPlotTab = uitab(app.TabGroup);
            app.LoadPlotTab.Title = 'Load Plot';

            % Create LoadPlot
            app.LoadPlot = uiaxes(app.LoadPlotTab);
            title(app.LoadPlot, 'Load')
            xlabel(app.LoadPlot, 'X')
            ylabel(app.LoadPlot, 'Y')
            zlabel(app.LoadPlot, 'Z')
            app.LoadPlot.Position = [21 232 660 364];

            % Create TareButton
            app.TareButton = uibutton(app.LoadPlotTab, 'push');
            app.TareButton.ButtonPushedFcn = createCallbackFcn(app, @TareButtonPushed, true);
            app.TareButton.Position = [142 191 100 23];
            app.TareButton.Text = 'Tare';

            % Create ClearLoadPlotButton
            app.ClearLoadPlotButton = uibutton(app.LoadPlotTab, 'push');
            app.ClearLoadPlotButton.ButtonPushedFcn = createCallbackFcn(app, @ClearLoadPlotButtonPushed, true);
            app.ClearLoadPlotButton.Position = [22 191 100 23];
            app.ClearLoadPlotButton.Text = 'Clear plot';

            % Create CropLoadSlider
            app.CropLoadSlider = uislider(app.LoadPlotTab, 'range');
            app.CropLoadSlider.ValueChangedFcn = createCallbackFcn(app, @CropLoadSliderValueChanged, true);
            app.CropLoadSlider.ValueChangingFcn = createCallbackFcn(app, @CropLoadSliderValueChanging, true);
            app.CropLoadSlider.Position = [27 38 500 3];

            % Create CropLoadButton
            app.CropLoadButton = uibutton(app.LoadPlotTab, 'push');
            app.CropLoadButton.ButtonPushedFcn = createCallbackFcn(app, @CropLoadButtonPushed, true);
            app.CropLoadButton.Position = [567 28 100 23];
            app.CropLoadButton.Text = 'Crop';

            % Create CalibrationPanel
            app.CalibrationPanel = uipanel(app.LoadPlotTab);
            app.CalibrationPanel.Title = 'Calibration';
            app.CalibrationPanel.Position = [351 95 330 119];

            % Create WeightinKgEditFieldLabel
            app.WeightinKgEditFieldLabel = uilabel(app.CalibrationPanel);
            app.WeightinKgEditFieldLabel.HorizontalAlignment = 'right';
            app.WeightinKgEditFieldLabel.Position = [5 65 73 22];
            app.WeightinKgEditFieldLabel.Text = 'Weight in Kg';

            % Create WeightinKgEditField
            app.WeightinKgEditField = uieditfield(app.CalibrationPanel, 'numeric');
            app.WeightinKgEditField.Limits = [0 1000];
            app.WeightinKgEditField.HorizontalAlignment = 'left';
            app.WeightinKgEditField.Position = [85 65 68 22];

            % Create CalibrateButton
            app.CalibrateButton = uibutton(app.CalibrationPanel, 'push');
            app.CalibrateButton.ButtonPushedFcn = createCallbackFcn(app, @CalibrateButtonPushed, true);
            app.CalibrateButton.Position = [160 65 100 23];
            app.CalibrateButton.Text = 'Calibrate';

            % Create OffsetEditFieldLabel
            app.OffsetEditFieldLabel = uilabel(app.CalibrationPanel);
            app.OffsetEditFieldLabel.Position = [10 36 37 22];
            app.OffsetEditFieldLabel.Text = 'Offset';

            % Create OffsetEditField
            app.OffsetEditField = uieditfield(app.CalibrationPanel, 'numeric');
            app.OffsetEditField.HorizontalAlignment = 'left';
            app.OffsetEditField.Position = [10 10 138 22];

            % Create ScaleEditFieldLabel
            app.ScaleEditFieldLabel = uilabel(app.CalibrationPanel);
            app.ScaleEditFieldLabel.Position = [160 36 35 22];
            app.ScaleEditFieldLabel.Text = 'Scale';

            % Create ScaleEditField
            app.ScaleEditField = uieditfield(app.CalibrationPanel, 'numeric');
            app.ScaleEditField.HorizontalAlignment = 'left';
            app.ScaleEditField.Position = [160 10 138 22];

            % Create MarkersCheckBox
            app.MarkersCheckBox = uicheckbox(app.LoadPlotTab);
            app.MarkersCheckBox.ValueChangedFcn = createCallbackFcn(app, @MarkersCheckBoxValueChanged, true);
            app.MarkersCheckBox.Text = 'Markers';
            app.MarkersCheckBox.Position = [268 193 65 22];
            app.MarkersCheckBox.Value = true;

            % Create ScanforCOMportsButton
            app.ScanforCOMportsButton = uibutton(app.UIFigure, 'push');
            app.ScanforCOMportsButton.ButtonPushedFcn = createCallbackFcn(app, @ScanforCOMportsButtonPushed, true);
            app.ScanforCOMportsButton.Position = [712 781 121 23];
            app.ScanforCOMportsButton.Text = 'Scan for COM ports';

            % Create AvailableCOMportsDropDownLabel
            app.AvailableCOMportsDropDownLabel = uilabel(app.UIFigure);
            app.AvailableCOMportsDropDownLabel.HorizontalAlignment = 'right';
            app.AvailableCOMportsDropDownLabel.Position = [842 782 115 22];
            app.AvailableCOMportsDropDownLabel.Text = 'Available COM ports';

            % Create AvailableCOMportsDropDown
            app.AvailableCOMportsDropDown = uidropdown(app.UIFigure);
            app.AvailableCOMportsDropDown.Items = {};
            app.AvailableCOMportsDropDown.Position = [972 782 100 22];
            app.AvailableCOMportsDropDown.Value = {};

            % Create ConnectionSwitchLabel
            app.ConnectionSwitchLabel = uilabel(app.UIFigure);
            app.ConnectionSwitchLabel.HorizontalAlignment = 'center';
            app.ConnectionSwitchLabel.Position = [852 753 66 22];
            app.ConnectionSwitchLabel.Text = 'Connection';

            % Create ConnectionSwitch
            app.ConnectionSwitch = uiswitch(app.UIFigure, 'slider');
            app.ConnectionSwitch.ValueChangedFcn = createCallbackFcn(app, @ConnectionSwitchValueChanged, true);
            app.ConnectionSwitch.Position = [944 754 45 20];

            % Create KnobLabel
            app.KnobLabel = uilabel(app.UIFigure);
            app.KnobLabel.HorizontalAlignment = 'center';
            app.KnobLabel.Position = [1050 612 25 22];
            app.KnobLabel.Text = '';

            % Create setRPMKnob
            app.setRPMKnob = uiknob(app.UIFigure, 'continuous');
            app.setRPMKnob.Limits = [0 240];
            app.setRPMKnob.ValueChangedFcn = createCallbackFcn(app, @setRPMKnobValueChanged, true);
            app.setRPMKnob.ValueChangingFcn = createCallbackFcn(app, @setRPMKnobValueChanging, true);
            app.setRPMKnob.Position = [1025 522 61 61];

            % Create delta0000mmLabel
            app.delta0000mmLabel = uilabel(app.UIFigure);
            app.delta0000mmLabel.Interpreter = 'latex';
            app.delta0000mmLabel.Position = [711 212 100 22];
            app.delta0000mmLabel.Text = '\delta \;= 0.000 mm';

            % Create deltaGauge
            app.deltaGauge = uigauge(app.UIFigure, 'linear');
            app.deltaGauge.Limits = [-10 10];
            app.deltaGauge.MajorTicks = [-10 -5 0 5 10];
            app.deltaGauge.Orientation = 'vertical';
            app.deltaGauge.Position = [715 244 56 200];

            % Create LoadCellSwitchLabel
            app.LoadCellSwitchLabel = uilabel(app.UIFigure);
            app.LoadCellSwitchLabel.HorizontalAlignment = 'center';
            app.LoadCellSwitchLabel.Position = [717 651 56 22];
            app.LoadCellSwitchLabel.Text = 'Load Cell';

            % Create LoadCellSwitch
            app.LoadCellSwitch = uiswitch(app.UIFigure, 'slider');
            app.LoadCellSwitch.Orientation = 'vertical';
            app.LoadCellSwitch.ValueChangedFcn = createCallbackFcn(app, @LoadCellSwitchValueChanged, true);
            app.LoadCellSwitch.Position = [722 688 20 45];

            % Create PositionSwitchLabel
            app.PositionSwitchLabel = uilabel(app.UIFigure);
            app.PositionSwitchLabel.HorizontalAlignment = 'center';
            app.PositionSwitchLabel.Position = [796 651 48 22];
            app.PositionSwitchLabel.Text = 'Position';

            % Create PositionSwitch
            app.PositionSwitch = uiswitch(app.UIFigure, 'slider');
            app.PositionSwitch.Orientation = 'vertical';
            app.PositionSwitch.ValueChangedFcn = createCallbackFcn(app, @PositionSwitchValueChanged, true);
            app.PositionSwitch.Position = [797 688 20 45];

            % Create VelocitySwitchLabel
            app.VelocitySwitchLabel = uilabel(app.UIFigure);
            app.VelocitySwitchLabel.HorizontalAlignment = 'center';
            app.VelocitySwitchLabel.Position = [873 651 46 22];
            app.VelocitySwitchLabel.Text = 'Velocity';

            % Create VelocitySwitch
            app.VelocitySwitch = uiswitch(app.UIFigure, 'slider');
            app.VelocitySwitch.Orientation = 'vertical';
            app.VelocitySwitch.ValueChangedFcn = createCallbackFcn(app, @VelocitySwitchValueChanged, true);
            app.VelocitySwitch.Position = [873 688 20 45];

            % Create SwitchLabel
            app.SwitchLabel = uilabel(app.UIFigure);
            app.SwitchLabel.HorizontalAlignment = 'center';
            app.SwitchLabel.Position = [765 427 25 22];
            app.SwitchLabel.Text = '';

            % Create RPMGauge
            app.RPMGauge = uigauge(app.UIFigure, 'circular');
            app.RPMGauge.Limits = [-240 240];
            app.RPMGauge.Position = [711 516 128 128];

            % Create RPMSwitch
            app.RPMSwitch = uiswitch(app.UIFigure, 'slider');
            app.RPMSwitch.Items = {'RPM', 'mm'};
            app.RPMSwitch.ValueChangedFcn = createCallbackFcn(app, @RPMSwitchValueChanged, true);
            app.RPMSwitch.Position = [754 464 45 20];
            app.RPMSwitch.Value = 'RPM';

            % Create SetRPMEditFieldLabel
            app.SetRPMEditFieldLabel = uilabel(app.UIFigure);
            app.SetRPMEditFieldLabel.HorizontalAlignment = 'right';
            app.SetRPMEditFieldLabel.Position = [961 472 63 22];
            app.SetRPMEditFieldLabel.Text = 'Set RPM';

            % Create SetRPMEditField
            app.SetRPMEditField = uieditfield(app.UIFigure, 'numeric');
            app.SetRPMEditField.Limits = [0 250];
            app.SetRPMEditField.ValueChangedFcn = createCallbackFcn(app, @SetRPMEditFieldValueChanged, true);
            app.SetRPMEditField.HorizontalAlignment = 'left';
            app.SetRPMEditField.Position = [1029 472 100 22];

            % Create MotorsSwitchLabel
            app.MotorsSwitchLabel = uilabel(app.UIFigure);
            app.MotorsSwitchLabel.HorizontalAlignment = 'center';
            app.MotorsSwitchLabel.Position = [1041 650 42 22];
            app.MotorsSwitchLabel.Text = 'Motors';

            % Create MotorsSwitch
            app.MotorsSwitch = uiswitch(app.UIFigure, 'rocker');
            app.MotorsSwitch.ValueChangedFcn = createCallbackFcn(app, @MotorsSwitchValueChanged, true);
            app.MotorsSwitch.Position = [1052 708 20 45];

            % Create EmergencySTOPButton
            app.EmergencySTOPButton = uibutton(app.UIFigure, 'push');
            app.EmergencySTOPButton.ButtonPushedFcn = createCallbackFcn(app, @EmergencySTOPButtonPushed, true);
            app.EmergencySTOPButton.BackgroundColor = [1 0 0];
            app.EmergencySTOPButton.FontWeight = 'bold';
            app.EmergencySTOPButton.Tooltip = {'Immediately breaks the motors to stop'};
            app.EmergencySTOPButton.Position = [841 456 100 38];
            app.EmergencySTOPButton.Text = {'Emergency'; 'STOP'};

            % Create Label_2
            app.Label_2 = uilabel(app.UIFigure);
            app.Label_2.HorizontalAlignment = 'center';
            app.Label_2.Position = [960 742 25 22];
            app.Label_2.Text = '';

            % Create StatusLamp
            app.StatusLamp = uilamp(app.UIFigure);
            app.StatusLamp.Position = [951 688 44 44];
            app.StatusLamp.Color = [0 0 0];

            % Create TareLocationButton
            app.TareLocationButton = uibutton(app.UIFigure, 'push');
            app.TareLocationButton.ButtonPushedFcn = createCallbackFcn(app, @TareLocationButtonPushed, true);
            app.TareLocationButton.Position = [711 184 110 30];
            app.TareLocationButton.Text = 'Tare Location';

            % Create DirectionKnobLabel
            app.DirectionKnobLabel = uilabel(app.UIFigure);
            app.DirectionKnobLabel.HorizontalAlignment = 'center';
            app.DirectionKnobLabel.Position = [881 522 52 22];
            app.DirectionKnobLabel.Text = 'Direction';

            % Create DirectionKnob
            app.DirectionKnob = uiknob(app.UIFigure, 'discrete');
            app.DirectionKnob.Items = {'Up', 'Stop', 'Down'};
            app.DirectionKnob.ValueChangedFcn = createCallbackFcn(app, @DirectionKnobValueChanged, true);
            app.DirectionKnob.Position = [879 550 60 60];
            app.DirectionKnob.Value = 'Stop';

            % Create Label
            app.Label = uilabel(app.UIFigure);
            app.Label.HorizontalAlignment = 'right';
            app.Label.Position = [11 130 25 22];
            app.Label.Text = '';

            % Create StatusBox
            app.StatusBox = uitextarea(app.UIFigure);
            app.StatusBox.Editable = 'off';
            app.StatusBox.Position = [11 134 690 20];
            app.StatusBox.Value = {'Status: Not connected to UTM'};

            % Create SaveDataButton
            app.SaveDataButton = uibutton(app.UIFigure, 'push');
            app.SaveDataButton.ButtonPushedFcn = createCallbackFcn(app, @SaveDataButtonPushed, true);
            app.SaveDataButton.Position = [961 321 100 23];
            app.SaveDataButton.Text = 'Save Data';

            % Create SpeedLabel
            app.SpeedLabel = uilabel(app.UIFigure);
            app.SpeedLabel.Position = [721 492 100 22];
            app.SpeedLabel.Text = 'Speed:';

            % Create Label_3
            app.Label_3 = uilabel(app.UIFigure);
            app.Label_3.HorizontalAlignment = 'center';
            app.Label_3.Position = [763 479 25 22];
            app.Label_3.Text = '';

            % Show the figure after all components are created
            app.UIFigure.Visible = 'on';
        end
    end

    % App creation and deletion
    methods (Access = public)

        % Construct app
        function app = UTM_exported

            % Create UIFigure and components
            createComponents(app)

            % Register the app with App Designer
            registerApp(app, app.UIFigure)

            % Execute the startup function
            runStartupFcn(app, @startupFcn)

            if nargout == 0
                clear app
            end
        end

        % Code that executes before app deletion
        function delete(app)

            % Delete UIFigure when app is deleted
            delete(app.UIFigure)
        end
    end
end