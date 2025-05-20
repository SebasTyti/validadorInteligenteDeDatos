SELECT TOP (1000) [idValidaciones]
      ,[idProcesoAdmin]
      ,[idUsuario]
      ,[FechaValidacion]
      ,[idEstado]
      ,[idPlantillasValidacion]
      ,[nombreArchivo]
  FROM [dbo].[Validaciones]


  truncate table [dbo].[Validaciones]

  DBCC CHECKIDENT ('Validaciones', RESEED, 0);